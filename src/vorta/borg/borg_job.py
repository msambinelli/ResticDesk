import json
import logging
import os
import select
import shlex
import shutil
import signal
import sys
import time
from collections import namedtuple
from datetime import datetime as dt
from subprocess import PIPE, Popen, TimeoutExpired
from threading import Lock

from PyQt6 import QtCore
from PyQt6.QtWidgets import QApplication

from vorta import application
from vorta.borg.jobs_manager import JobInterface
from vorta.i18n import trans_late, translate
from vorta.keyring.abc import VortaKeyring
from vorta.keyring.db import VortaDBKeyring
from vorta.store.models import EventLogModel
from vorta.utils import borg_compat, pretty_bytes

keyring_lock = Lock()
db_lock = Lock()
logger = logging.getLogger(__name__)

FakeRepo = namedtuple('Repo', ['url', 'name', 'id', 'extra_borg_arguments', 'encryption'])
FakeProfile = namedtuple('FakeProfile', ['id', 'repo', 'name', 'ssh_key'])

"""
All methods in this class must be thread safe. Particularly,
I strongly unadvised global variable and class variables.
Sqlite access are thread-safe because peewee is thread-safe.
The method prepare is not thread-safe because of keyring and I don't know why. That's why I added a
temporary mutex.
"""


class BorgJob(JobInterface):
    """
    Base class to run `borg` command line jobs. If a command needs more pre- or post-processing
    it should subclass `BorgJob`.
    """

    updated = QtCore.pyqtSignal(str)
    result = QtCore.pyqtSignal(dict)
    keyring = None  # Store keyring to minimize imports

    def __init__(self, cmd, params, site="default"):
        """
        Thread to run Borg operations in.

        :param cmd: Borg command line
        :param params: Pass options that were used to build cmd and may be needed to
                       process the result.
        :param site: For scheduler. Only one job can run per site at one time. Site is
                     usually the repository ID, or 'default' for misc Borg commands.
        """

        super().__init__()
        self.site_id = site
        self.app: application.VortaApp = QApplication.instance()

        # Declare labels here for translation
        self.category_label = {
            "files": trans_late("BorgJob", "Files"),
            "original": trans_late("BorgJob", "Original"),
            "deduplicated": trans_late("BorgJob", "Deduplicated"),
            "compressed": trans_late("BorgJob", "Compressed"),
        }

        cmd[0] = self.prepare_bin()

        # Add extra Borg args to command. Never pass None.
        extra_args_str = params.get('extra_borg_arguments')
        if extra_args_str is not None and len(extra_args_str) > 0:
            extra_args = shlex.split(extra_args_str)
            cmd = cmd[:2] + extra_args + cmd[2:]

        env = os.environ.copy()
        env['RESTIC_REPOSITORY'] = params.get('repo_url', '')
        env['RESTIC_PASSWORD'] = ''

        if 'additional_env' in params:
            env = {**env, **params['additional_env']}

        password = params.get('password')
        if password is not None:
            env['RESTIC_PASSWORD'] = password

        if env.get('RESTIC_PASSWORD_COMMAND', False):
            env.pop('RESTIC_PASSWORD', None)

        ssh_key = params.get('ssh_key')
        if ssh_key is not None:
            ssh_key_path = os.path.expanduser(f'~/.ssh/{ssh_key}')
            env['RESTIC_PASSWORD_COMMAND'] = env.get('RESTIC_PASSWORD_COMMAND', '')

        self.env = env
        self.cmd = cmd
        self.cwd = params.get('cwd', None)
        self.params = params
        self.process = None
        self.cleanup_files = params.get('cleanup_files', [])

    def repo_id(self):
        return self.site_id

    def cancel(self):
        logger.debug("Cancel job on site %s", self.site_id)
        if self.process is not None:
            self.process.send_signal(signal.SIGINT)
            try:
                self.process.wait(timeout=3)
            except TimeoutExpired:
                try:
                    os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
                except ProcessLookupError:
                    pass

    @classmethod
    def prepare(cls, profile):
        """
        Prepare for running Borg. This function in the base class should be called from all
        subclasses and calls that define their own `cmd`.

        The `prepare()` step does these things:
        - validate if all conditions to run command are met
        - build borg command

        `prepare()` is run 2x. First at the global level and then for each subcommand.

        :return: dict(ok: book, message: str)
        """
        ret = {'ok': False}

        if cls.prepare_bin() is None:
            ret['message'] = trans_late('messages', 'Restic binary was not found.')
            return ret

        if profile.repo is None:
            ret['message'] = trans_late('messages', 'Select a backup repository first.')
            return ret

        if not borg_compat.check('JSON_LOG'):
            ret['message'] = trans_late('messages', 'Your Restic version is too old.')
            return ret

        # Try to get password from chosen keyring backend.
        with keyring_lock:
            cls.keyring = VortaKeyring.get_keyring()
            logger.debug("Using %s keyring to store passwords.", cls.keyring.__class__.__name__)
            ret['password'] = cls.keyring.get_password('vorta-repo', profile.repo.url)

            # Check if keyring is locked
            if profile.repo.encryption != 'none' and not cls.keyring.is_unlocked:
                ret['message'] = trans_late(
                    'messages',
                    'Please unlock your system password manager or disable it under Settings',
                )
                return ret

            # Try to fall back to DB Keyring, if we use the system keychain.
            if ret['password'] is None and cls.keyring.is_system:
                logger.debug('Password not found in primary keyring. Falling back to VortaDBKeyring.')
                ret['password'] = VortaDBKeyring().get_password('vorta-repo', profile.repo.url)

                # Give warning and continue if password is found there.
                if ret['password'] is not None:
                    logger.warning(
                        'Found password in database, but secure storage was available. '
                        'Consider re-adding the repo to use it.'
                    )

        # Password is required for encryption, cannot continue
        if ret['password'] is None and not isinstance(profile.repo, FakeRepo) and profile.repo.encryption != 'none':
            ret['message'] = trans_late(
                'messages',
                "Your repo passphrase was stored in a password manager which is no longer available.\n"
                "Try unlinking and re-adding your repo.",
            )
            return ret

        ret['ssh_key'] = profile.ssh_key
        ret['repo_id'] = profile.repo.id
        ret['repo_url'] = profile.repo.url
        ret['repo_name'] = profile.repo.name
        ret['extra_borg_arguments'] = profile.repo.extra_borg_arguments
        ret['profile_name'] = profile.name
        ret['profile_id'] = profile.id

        ret['ok'] = True
        ret['cleanup_files'] = []

        return ret

    @classmethod
    def prepare_bin(cls):
        """Find restic binary."""
        # On MacOS, the PATH environment variable does not seem to be set when run as a pyinstaller binary.
        # More info at https://github.com/borgbase/vorta/issues/2100
        # Set the path to also find homebrew installs.
        if sys.platform == 'darwin':
            current_path = os.environ.get("PATH", "/usr/bin:/bin")
            os.environ["PATH"] = f"{current_path}:/opt/homebrew/bin:/usr/local/bin"
        restic_in_path = shutil.which('restic')

        if restic_in_path:
            return restic_in_path
        return None

    def run(self):
        self.started_event()
        with db_lock:
            log_entry = EventLogModel(
                category=self.params.get('category', 'user'),
                subcommand=self.cmd[1],
                profile=self.params.get('profile_id', None),
            )
            log_entry.save()

            # logs: put cmd arguments with special strings in quotation marks
            quote_strings = [' ', '*', '?', 're:']
            cmd_args_to_log = self.cmd[:]
            for i, arg in enumerate(cmd_args_to_log):
                if any(quotestr in arg for quotestr in quote_strings):
                    cmd_args_to_log[i] = "'" + arg + "'"  # add quotes

            logger.info('Running command: %s', ' '.join(cmd_args_to_log))
            del cmd_args_to_log

        p = Popen(
            self.cmd,
            stdout=PIPE,
            stderr=PIPE,
            bufsize=1,
            universal_newlines=True,
            env=self.env,
            cwd=self.cwd,
            start_new_session=True,
        )
        error_messages = []  # List of error messages included in the result

        self.process = p

        # Prevent blocking of stdout/err. Via https://stackoverflow.com/a/7730201/3983708
        try:
            os.set_blocking(p.stdout.fileno(), False)
            os.set_blocking(p.stderr.fileno(), False)
        except (AttributeError, OSError, ValueError):
            # Some tests mock stdout/stderr without real file descriptors.
            pass

        def read_async(fd):
            try:
                if isinstance(fd, str):
                    return fd
                return fd.read()
            except (IOError, TypeError, ValueError, AttributeError):
                return ''

        stdout = []
        json_events = []
        use_select = True
        while True:
            # Wait for new output
            if use_select:
                try:
                    select.select([p.stdout, p.stderr], [], [], 0.1)
                except (TypeError, ValueError):
                    # Test doubles may not expose real file descriptors.
                    use_select = False
            else:
                time.sleep(0.05)

            stdout.append(read_async(p.stdout))
            stderr = read_async(p.stderr)
            if stderr:
                for line in stderr.split('\n'):
                    try:
                        parsed = json.loads(line)
                        if isinstance(parsed, dict):
                            json_events.append(parsed)

                        if parsed.get('type') == 'log_message':
                            context = {
                                'msgid': parsed.get('msgid'),
                                'repo_url': self.params['repo_url'],
                                'profile_name': self.params.get('profile_name'),
                                'cmd': self.params['cmd'][1],
                            }
                            self.app.backup_log_event.emit(
                                f'[{self.params["profile_name"]}] {parsed["levelname"]}: {parsed["message"]}', context
                            )
                            level_int = getattr(logging, parsed["levelname"])
                            logger.log(level_int, parsed["message"])

                            if level_int >= logging.WARNING:
                                # Append log to list of error messages
                                error_messages.append((level_int, parsed["message"]))

                        elif parsed.get('type') == 'file_status':
                            self.app.backup_log_event.emit(
                                f'[{self.params["profile_name"]}] {parsed["path"]} ({parsed["status"]})', {}
                            )
                        elif parsed.get('type') == 'progress_percent' and parsed.get("message"):
                            self.app.backup_log_event.emit(f'[{self.params["profile_name"]}] {parsed["message"]}', {})
                        elif parsed.get('type') == 'archive_progress' and not parsed.get('finished', False):
                            msg = (
                                f"{translate('BorgJob','Files')}: {parsed['nfiles']}, "
                                f"{translate('BorgJob','Original')}: {pretty_bytes(parsed['original_size'])}, "
                                # f"{translate('BorgJob','Compressed')}: {pretty_bytes(parsed['compressed_size'])}, "
                                f"{translate('BorgJob','Deduplicated')}: {pretty_bytes(parsed.get('deduplicated_size', 0))}"  # noqa: E501
                            )
                            self.app.backup_progress_event.emit(f"[{self.params['profile_name']}] {msg}")
                        elif parsed.get('message_type') in {'status', 'summary', 'error'}:
                            if parsed.get('message_type') == 'status':
                                files_done = parsed.get('files_done', 0)
                                bytes_done = parsed.get('bytes_done', 0)
                                msg = f"{translate('BorgJob','Files')}: {files_done}, {translate('BorgJob','Deduplicated')}: {pretty_bytes(bytes_done)}"
                                self.app.backup_progress_event.emit(f"[{self.params['profile_name']}] {msg}")
                    except json.decoder.JSONDecodeError:
                        msg = line.strip()
                        if msg:  # Log only if there is something to log.
                            self.app.backup_log_event.emit(f'[{self.params["profile_name"]}] {msg}', {})
                            logger.warning(msg)

            if p.poll() is not None:
                time.sleep(0.1)
                stdout.append(read_async(p.stdout))
                break

        result = {
            'params': self.params,
            'returncode': self.process.returncode,
            'cmd': self.cmd,
            'errors': error_messages,
        }
        stdout = ''.join(stdout)

        try:
            result['data'] = json.loads(stdout)
        except ValueError:
            parsed_lines = []
            for line in stdout.splitlines():
                try:
                    parsed_lines.append(json.loads(line))
                except ValueError:
                    continue
            result['data'] = parsed_lines if parsed_lines else stdout

        log_entry.returncode = p.returncode
        log_entry.repo_url = self.params.get('repo_url', None)
        log_entry.end_time = dt.now()
        with db_lock:
            log_entry.save()
            self.process_result(result)

        self.finished_event(result)
        for tmpfile in self.cleanup_files:
            tmpfile.close()

    def process_result(self, result):
        pass

    def started_event(self):
        self.updated.emit(self.tr('Task started'))

    def finished_event(self, result):
        self.result.emit(result)
