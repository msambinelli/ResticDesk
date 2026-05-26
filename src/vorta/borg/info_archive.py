from datetime import datetime as dt

from vorta.store.models import ArchiveModel

from .borg_job import BorgJob


class BorgInfoArchiveJob(BorgJob):
    def started_event(self):
        self.app.backup_started_event.emit()
        self.app.backup_progress_event.emit(f"[{self.params['profile_name']}] {self.tr('Refreshing archive…')}")

    def finished_event(self, result):
        self.app.backup_finished_event.emit(result)
        self.result.emit(result)
        self.app.backup_progress_event.emit(f"[{self.params['profile_name']}] {self.tr('Refreshing archive done.')}")

    @classmethod
    def prepare(cls, profile, archive_name):
        ret = super().prepare(profile)
        if not ret['ok']:
            return ret

        ret['ok'] = True
        ret['cmd'] = ['restic', 'snapshots', '--json', '--tag', archive_name, '-r', profile.repo.url]
        ret['archive_name'] = archive_name

        return ret

    def process_result(self, result):
        if result['returncode'] == 0:
            snapshots = result['data'] if isinstance(result['data'], list) else []
            repo_id = result['params']['repo_id']
            if not snapshots:
                return
            latest = snapshots[-1]
            archive = ArchiveModel.get_or_none(name=result['params']['archive_name'], repo=repo_id)
            if archive is None:
                return
            archive.snapshot_id = latest.get('short_id') or latest.get('id') or archive.snapshot_id
            snapshot_time = latest.get('time')
            if snapshot_time:
                archive.time = dt.fromisoformat(snapshot_time.replace('Z', '+00:00')).astimezone().replace(tzinfo=None)
            archive.save()
