from datetime import datetime as dt

from vorta.store.models import ArchiveModel, RepoModel
from .borg_job import BorgJob


class BorgListRepoJob(BorgJob):
    def started_event(self):
        self.app.backup_started_event.emit()
        self.app.backup_progress_event.emit(f"[{self.params['profile_name']}] {self.tr('Refreshing archives…')}")

    def finished_event(self, result):
        self.app.backup_finished_event.emit(result)
        self.result.emit(result)
        self.app.backup_progress_event.emit(f"[{self.params['profile_name']}] {self.tr('Refreshing archives done.')}")

    @classmethod
    def prepare(cls, profile):
        ret = super().prepare(profile)
        if not ret['ok']:
            return ret
        else:
            ret['ok'] = False  # Set back to false, so we can do our own checks here.

        cmd = ['restic', 'snapshots', '--json', '-r', f'{profile.repo.url}']

        ret['ok'] = True
        ret['cmd'] = cmd

        return ret

    def process_result(self, result):
        if result['returncode'] == 0:
            repo_url = result['params']['repo_url']
            repo, _ = RepoModel.get_or_create(url=repo_url)
            remote_snapshots = result['data'] if isinstance(result['data'], list) else []
            remote_archives = [
                {
                    'id': snap.get('short_id') or snap.get('id'),
                    'name': (snap.get('tags') or [snap.get('short_id') or snap.get('id')])[0],
                    'time': snap.get('time'),
                }
                for snap in remote_snapshots
                if isinstance(snap, dict)
            ]

            # Delete archives that don't exist on the remote side
            for archive in ArchiveModel.select().where(ArchiveModel.repo == repo.id):
                if not list(filter(lambda s: s['id'] == archive.snapshot_id, remote_archives)):
                    archive.delete_instance()

            # Add remote archives we don't have locally.
            for archive in remote_archives:
                new_archive, _ = ArchiveModel.get_or_create(
                    snapshot_id=archive['id'],
                    repo=repo.id,
                    defaults={
                        'name': archive['name'],
                        # Convert to local time (for Borg 2.x UTC timestamps) before storing as naive datetime
                        'time': dt.fromisoformat(archive['time']).astimezone().replace(tzinfo=None),
                    },
                )
                new_archive.save()
