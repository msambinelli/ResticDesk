from vorta.i18n import trans_late
from vorta.store.models import RepoModel
from .borg_job import BorgJob, FakeProfile, FakeRepo


class BorgInfoRepoJob(BorgJob):
    def started_event(self):
        self.updated.emit(self.tr('Validating existing repo…'))

    @classmethod
    def prepare(cls, params):
        """
        Used to validate existing repository when added.
        """

        # Build fake profile because we don't have it in the DB yet. Assume unencrypted.
        profile = FakeProfile(
            999,
            FakeRepo(params['repo_url'], params['repo_name'], 999, params['extra_borg_arguments'], 'none'),
            'New Repo',
            params['ssh_key'],
        )

        ret = super().prepare(profile)
        if not ret['ok']:
            return ret
        else:
            ret['ok'] = False  # Set back to false, so we can do our own checks here.

        cmd = ["restic", "snapshots", "--json", "-r", profile.repo.url]

        ret['additional_env'] = {}

        ret['password'] = params['password']  # Empty password is '', which disables prompt
        if params['password'] != '':
            # Cannot tell if repo has encryption, assuming based off of password
            if not cls.keyring.is_unlocked:
                ret['message'] = trans_late('messages', 'Please unlock your password manager.')
                return ret

        ret['repo_name'] = params['repo_name']
        ret['ok'] = True
        ret['cmd'] = cmd

        return ret

    def process_result(self, result):
        if result['returncode'] == 0:
            new_repo, _ = RepoModel.get_or_create(
                url=result['cmd'][-1], defaults={'name': result['params']['repo_name']}
            )
            new_repo.total_size = None
            new_repo.unique_size = None
            new_repo.total_unique_chunks = None
            new_repo.encryption = 'repokey'
            if new_repo.encryption != 'none':
                self.keyring.set_password("vorta-repo", new_repo.url, result['params']['password'])
            new_repo.extra_borg_arguments = result['params']['extra_borg_arguments']

            new_repo.save()
