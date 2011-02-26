"""
Mercurial hook to check that individual changesets don't happen on a
forbidden branch.

To use the changeset hook in a local repository, include something like the
following in your hgrc file.

[hooks]
pretxnchangegroup.checkbranch = python:/home/hg/repos/hooks/checkbranch.py:hook
"""

from mercurial.node import bin
from mercurial import util


def hook(ui, repo, node, **kwargs):
    n = bin(node)
    start = repo.changelog.rev(n)
    end = len(repo.changelog)
    failed = False
    for rev in xrange(start, end):
        n = repo.changelog.node(rev)
        ctx = repo[n]
        branch = ctx.branch()
        if branch in ('trunk', 'legacy-trunk',
                      '2.0', '2.1', '2.2', '2.3', '2.4', '3.0'):
            ui.warn(' - changeset %s on disallowed branch %r!\n'
                  % (ctx, branch))
            failed = True
    if failed:
        ui.warn('* Please strip the offending changeset(s)\n'
                '* and re-do them, if needed, on another branch!\n')
        return True

