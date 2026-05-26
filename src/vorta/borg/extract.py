from PyQt6.QtCore import QModelIndex, Qt

from vorta.views.dialogs.archive.extract import ExtractTree, FileData
from vorta.views.partials.treemodel import FileSystemItem, path_to_str

from .borg_job import BorgJob


class BorgExtractJob(BorgJob):
    def started_event(self):
        self.app.backup_started_event.emit()
        self.app.backup_progress_event.emit(
            f"[{self.params['profile_name']}] {self.tr('Downloading files from archive…')}"
        )

    def finished_event(self, result):
        self.app.backup_finished_event.emit(result)
        self.result.emit(result)
        self.app.backup_progress_event.emit(
            f"[{self.params['profile_name']}] {self.tr('Restored files from archive.')}"
        )

    @classmethod
    def prepare(cls, profile, archive_name, model: ExtractTree, destination_folder):
        ret = super().prepare(profile)
        if not ret['ok']:
            return ret
        else:
            ret['ok'] = False  # Set back to false, so we can do our own checks here.

        cmd = ['restic', 'restore', 'latest', '--json', '--tag', archive_name, '--target', destination_folder]

        # process selected items
        # all items will be excluded beside the one actively selected in the
        # dialog.
        # Unselected (and excluded) parent folders will be restored by borg
        # but without the metadata stored in the archive.
        include_paths = []

        indexes = [QModelIndex()]
        while indexes:
            index = indexes.pop()

            for i in range(model.rowCount(index)):
                new_index = model.index(i, 0, index)
                indexes.append(new_index)

                item: FileSystemItem[FileData] = new_index.internalPointer()
                if item.data.checkstate == Qt.CheckState.Checked:
                    include_paths.append(path_to_str(item.path))

        for include_path in include_paths:
            cmd.extend(['--include', include_path])

        ret['ok'] = True
        ret['cmd'] = cmd
        ret['cwd'] = destination_folder

        return ret

    def process_result(self, result: dict):
        pass
