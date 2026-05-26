import json

from .borg_job import BorgJob


class BorgListArchiveJob(BorgJob):
    def started_event(self):
        self.app.backup_started_event.emit()
        self.app.backup_progress_event.emit(f"[{self.params['profile_name']}] {self.tr('Getting archive content…')}")

    def finished_event(self, result):
        self.app.backup_finished_event.emit(result)
        self.app.backup_progress_event.emit(
            f"[{self.params['profile_name']}] {self.tr('Done getting archive content.')}"
        )
        self.result.emit(result)

    @classmethod
    def prepare(cls, profile, archive_name):
        ret = super().prepare(profile)
        if not ret['ok']:
            return ret

        ret['archive_name'] = archive_name
        ret['cmd'] = ['restic', 'ls', '--json', 'latest', '--tag', archive_name, '-r', profile.repo.url]

        ret['ok'] = True

        return ret

    def process_result(self, result):
        if result['returncode'] != 0:
            return
        events = result['data'] if isinstance(result['data'], list) else []
        normalized = []
        for event in events:
            if not isinstance(event, dict) or event.get('struct_type') != 'node':
                continue
            node_type = event.get('type', 'file')
            mode_prefix = {'dir': 'd', 'symlink': 'l', 'file': '-'}.get(node_type, '-')
            normalized.append(
                {
                    'path': event.get('path', ''),
                    'size': event.get('size', 0),
                    'mode': mode_prefix + '---------',
                    'user': str(event.get('uid', '')),
                    'group': str(event.get('gid', '')),
                    'healthy': True,
                    'isomtime': event.get('mtime', ''),
                    'source': event.get('linktarget'),
                }
            )
        result['data'] = '\n'.join(json.dumps(item) for item in normalized)
