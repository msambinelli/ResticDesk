from collections import namedtuple

from vorta.borg.borg_job import BorgJob
from vorta.borg.diff import BorgDiffJob
from vorta.borg.rename import BorgRenameJob


Repo = namedtuple('Repo', ['url'])
Profile = namedtuple('Profile', ['repo'])


def test_diff_prepare_returns_not_ok_with_restic(monkeypatch):
    monkeypatch.setattr(BorgJob, 'prepare', classmethod(lambda cls, profile: {'ok': True}))
    profile = Profile(repo=Repo(url='/tmp/repo'))

    ret = BorgDiffJob.prepare(profile, 'snap-1', 'snap-2')

    assert ret['ok'] is False
    assert 'unavailable with Restic backend' in ret['message']


def test_rename_prepare_returns_not_ok_with_restic(monkeypatch):
    monkeypatch.setattr(BorgJob, 'prepare', classmethod(lambda cls, profile: {'ok': True}))
    profile = Profile(repo=Repo(url='/tmp/repo'))

    ret = BorgRenameJob.prepare(profile, 'snap-old', 'snap-new')

    assert ret['ok'] is False
    assert 'not supported by Restic' in ret['message']
