"""
Mercurial hook to check that individual changesets don't happen on a
forbidden branch.

To use the changeset hook in a local repository, include something like the
following in your hgrc file.

[hooks]
pretxncommit.checkbranch = python:/home/hg/repos/hooks/checkbranch.py:hook
"""

from mercurial import util


def hook(ui, repo, node, **kwargs):
    ctx = repo[node]
    branch = ctx.branch()
    if branch in ('trunk', 'legacy-trunk',
                  '2.0', '2.1', '2.2', '2.3', '2.4', '3.0'):
        raise util.Abort('changeset %s on disallowed branch %r, '
                         'please strip your changeset and '
                         're-do it on another branch '
                         % (ctx, branch))
