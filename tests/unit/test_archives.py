from collections import namedtuple

import psutil
import pytest
from PyQt6 import QtCore
from PyQt6.QtWidgets import QMenu
from test_constants import TEST_TEMP_DIR

import vorta.borg
import vorta.utils
import vorta.views.archive_tab
from vorta.store.models import ArchiveModel, BackupProfileModel


class MockFileDialog:
    def open(self, func):
        func()

    def selectedFiles(self):
        return [TEST_TEMP_DIR]


def test_prune_intervals(qapp, qtbot):
    prune_intervals = ['hour', 'day', 'week', 'month', 'year']
    main = qapp.main_window
    tab = main.archiveTab
    profile = BackupProfileModel.get(id=1)

    for i in prune_intervals:
        getattr(tab, f'prune_{i}').setValue(9)
        tab.save_prune_setting(None)
        profile = profile.refresh()
        assert getattr(profile, f'prune_{i}') == 9


def test_populate_does_not_overwrite_prune_keep_within(qapp, qtbot):
    """Loading a profile must not fire save_prune_setting and overwrite
    prune_keep_within with stale QLineEdit text (#2493)."""
    main = qapp.main_window
    tab = main.archiveTab
    profile = BackupProfileModel.get(id=1)
    profile.prune_keep_within = '10H'
    profile.prune_hour = 7
    profile.save()

    # Simulate stale UI state: a spinbox value differs from the DB (so the
    # setValue call inside populate_from_profile would otherwise fire
    # valueChanged -> save_prune_setting) and the prune_keep_within QLineEdit
    # holds stale text from another profile. Block signals while setting this
    # up so the pre-state itself doesn't overwrite the DB values just saved.
    tab.prune_hour.blockSignals(True)
    try:
        tab.prune_hour.setValue(1)
    finally:
        tab.prune_hour.blockSignals(False)
    tab.prune_keep_within.setText('')

    tab.populate_from_profile()

    profile = profile.refresh()
    assert profile.prune_keep_within == '10H'
    assert tab.prune_keep_within.text() == '10H'


def test_repo_list(qapp, qtbot, mocker, borg_json_output, archive_env):
    main, tab = archive_env

    stdout = """
[
  {"id":"1111111111111111111111111111111111111111111111111111111111111111","short_id":"11111111","time":"2024-01-01T10:00:00Z","tags":["test-archive"]},
  {"id":"2222222222222222222222222222222222222222222222222222222222222222","short_id":"22222222","time":"2024-01-01T11:00:00Z","tags":["test-archive1"]}
]
"""
    stderr = ""
    popen_result = mocker.MagicMock(stdout=stdout, stderr=stderr, returncode=0)
    mocker.patch.object(vorta.borg.borg_job, 'Popen', return_value=popen_result)

    tab.refresh_archive_list()
    qtbot.waitUntil(lambda: not tab.bCheck.isEnabled(), **pytest._wait_defaults)
    assert not tab.bCheck.isEnabled()

    qtbot.waitUntil(lambda: 'Refreshing archives done.' in main.progressText.text(), **pytest._wait_defaults)
    assert ArchiveModel.select().count() >= 1
    assert 'Refreshing archives done.' in main.progressText.text()
    assert tab.bCheck.isEnabled()


def test_repo_prune(qapp, qtbot, mocker, borg_json_output, archive_env):
    main, tab = archive_env

    stdout, stderr = borg_json_output('prune')
    popen_result = mocker.MagicMock(stdout=stdout, stderr=stderr, returncode=0)
    mocker.patch.object(vorta.borg.borg_job, 'Popen', return_value=popen_result)

    qtbot.mouseClick(tab.bPrune, QtCore.Qt.MouseButton.LeftButton)

    qtbot.waitUntil(lambda: 'Refreshing archives done.' in main.progressText.text(), **pytest._wait_defaults)


def test_repo_compact(qapp, qtbot, mocker, borg_json_output, archive_env):
    pytest.skip("Compact flow is Borg-specific and currently disabled on Restic backend.")


def test_check(qapp, mocker, borg_json_output, qtbot, archive_env):
    main, tab = archive_env

    stdout, stderr = borg_json_output('check')
    popen_result = mocker.MagicMock(stdout=stdout, stderr=stderr, returncode=0)
    mocker.patch.object(vorta.borg.borg_job, 'Popen', return_value=popen_result)

    qtbot.mouseClick(tab.bCheck, QtCore.Qt.MouseButton.LeftButton)
    success_text = 'INFO: Archive consistency check complete'
    qtbot.waitUntil(lambda: success_text in main.logText.text(), **pytest._wait_defaults)


def test_mount(qapp, qtbot, mocker, borg_json_output, monkeypatch, choose_file_dialog, archive_env):
    def psutil_disk_partitions(**kwargs):
        DiskPartitions = namedtuple('DiskPartitions', ['device', 'mountpoint', 'fstype'])
        return [DiskPartitions('resticfs', TEST_TEMP_DIR, 'fuse')]

    monkeypatch.setattr(psutil, "disk_partitions", psutil_disk_partitions)
    main, tab = archive_env
    tab.archiveTable.selectRow(0)

    stdout, stderr = borg_json_output('prune')  # TODO: fully mock mount command?
    popen_result = mocker.MagicMock(stdout=stdout, stderr=stderr, returncode=0)
    mocker.patch.object(vorta.borg.borg_job, 'Popen', return_value=popen_result)

    monkeypatch.setattr("vorta.views.archive.archive_mount.choose_file_dialog", choose_file_dialog)

    tab.archive_mount.bmountarchive_clicked()
    qtbot.waitUntil(
        lambda: 'Mounting a single archive is not supported by Restic' in tab.mountErrors.text(),
        **pytest._wait_defaults,
    )

    tab.archive_mount.bmountrepo_clicked()
    qtbot.waitUntil(lambda: tab.mountErrors.text().startswith('Mounted'), **pytest._wait_defaults)

    tab.archive_mount.bmountrepo_clicked()
    qtbot.waitUntil(lambda: tab.mountErrors.text().startswith('Un-mounted successfully.'), **pytest._wait_defaults)


def test_archive_extract(qapp, qtbot, mocker, borg_json_output, archive_env):
    main, tab = archive_env
    tab.archiveTable.selectRow(0)
    stdout = """
{"struct_type":"node","path":"home","type":"dir","size":0,"uid":1000,"gid":1000,"mtime":"2024-01-01T10:00:00Z"}
{"struct_type":"node","path":"home/user/file.txt","type":"file","size":123,"uid":1000,"gid":1000,"mtime":"2024-01-01T10:00:01Z"}
"""
    stderr = ""
    popen_result = mocker.MagicMock(stdout=stdout, stderr=stderr, returncode=0)
    mocker.patch.object(vorta.borg.borg_job, 'Popen', return_value=popen_result)
    tab.archive_extract.extract_action()

    qtbot.waitUntil(lambda: hasattr(tab, '_window'), **pytest._wait_defaults)

    model = tab._window.model
    assert model.root.children[0].subpath == 'home'
    assert 'test-archive, 2000' in tab._window.archiveNameLabel.text()


def test_archive_delete(qapp, qtbot, mocker, borg_json_output, archive_env):
    main, tab = archive_env

    tab.archiveTable.selectRow(0)
    stdout, stderr = borg_json_output('delete')
    popen_result = mocker.MagicMock(stdout=stdout, stderr=stderr, returncode=0)
    mocker.patch.object(vorta.borg.borg_job, 'Popen', return_value=popen_result)
    mocker.patch.object(vorta.views.archive_tab.ArchiveTab, 'confirm_dialog', lambda x, y, z: True)
    tab.delete_action()
    qtbot.waitUntil(lambda: 'Archive deleted.' in main.progressText.text(), **pytest._wait_defaults)
    assert ArchiveModel.select().count() == 1
    assert tab.archiveTable.rowCount() == 1


def test_archive_copy(qapp, qtbot, monkeypatch, mocker, archive_env):
    main, tab = archive_env

    # mock the clipboard to ensure no changes are made to it during testing
    mocker.patch.object(qapp.clipboard(), "setMimeData")
    clipboard_spy = mocker.spy(qapp.clipboard(), "setMimeData")

    # test 'archive_copy()' by passing it an index to copy
    index = tab.archiveTable.model().index(0, 0)
    tab.archive_copy(index)
    assert clipboard_spy.call_count == 1
    actual_data = clipboard_spy.call_args[0][0]  # retrieves the QMimeData() object used in method call
    assert actual_data.text() == "test-archive"

    # test 'archive_copy()' by selecting a row to copy
    tab.archiveTable.selectRow(1)
    tab.archive_copy()
    assert clipboard_spy.call_count == 2
    actual_data = clipboard_spy.call_args[0][0]  # retrieves the QMimeData() object used in method call
    assert actual_data.text() == "test-archive1"


def test_refresh_archive_info(qapp, qtbot, mocker, borg_json_output, archive_env):
    main, tab = archive_env
    tab.archiveTable.selectRow(0)
    stdout, stderr = borg_json_output('info')
    popen_result = mocker.MagicMock(stdout=stdout, stderr=stderr, returncode=0)
    mocker.patch.object(vorta.borg.borg_job, 'Popen', return_value=popen_result)

    with qtbot.waitSignal(tab.bRefreshArchive.clicked, timeout=5000):
        qtbot.mouseClick(tab.bRefreshArchive, QtCore.Qt.MouseButton.LeftButton)

    qtbot.waitUntil(lambda: tab.mountErrors.text() == 'Refreshed archives.', **pytest._wait_defaults)


def test_inline_archive_rename_not_supported_with_restic(qapp, qtbot, archive_env):
    """
    Tests the functionality of in-line renaming an archive.
    """
    main, tab = archive_env

    assert not tab.bRename.isVisible()


def test_archiveitem_contextmenu(qapp, qtbot, archive_env):
    main, tab = archive_env

    tab.archiveTable.selectRow(0)
    pos = tab.archiveTable.visualRect(tab.archiveTable.model().index(0, 0)).center()
    tab.archiveTable.customContextMenuRequested.emit(pos)
    qtbot.waitUntil(lambda: tab.archiveTable.findChild(QMenu) is not None, **pytest._wait_defaults)

    context_menu = tab.archiveTable.findChild(QMenu)

    assert context_menu is not None
    action_labels = [a.text() for a in context_menu.actions()]
    assert 'Copy' in action_labels
