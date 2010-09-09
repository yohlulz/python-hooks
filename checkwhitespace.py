"""
Mercurial hooks to check changegroups and individual changesets for
whitespace issues.

To use the changeset hook in a local repository, include something like the
following in your hgrc file, and make sure that this file (i.e.,
check_whitespace.py) is in your PYTHONPATH.

[hooks]
pretxncommit.whitespace = python:checkwhitespace.check_whitespace_single
"""

from StringIO import StringIO
from reindent import Reindenter
from mercurial import revset
from mercurial import node
from mercurial import cmdutil

def check_file(ui, repo, path, rev):
    """Check a particular (file, revision) pair for whitespace issues.

    Return True if whitespace problems exist, else False.

    """
    ui.debug("checking file %s at revision %s for whitespace issues\n" %
             (path, node.short(repo[rev].node())))

    # Check Python files using reindent.py
    if path.endswith('.py'):
        content = StringIO(repo[rev][path].data())
        reindenter = Reindenter(content)
        if reindenter.run():
            ui.warn("file %s is not whitespace-normalized\n" % path)
            return True

    # Check ReST files for tabs and trailing whitespace
    elif path.endswith('.rst'):
        lines = StringIO(repo[rev][path].data()).readlines()
        for line in lines:
            if '\t' in line:
                ui.warn("file %s contains tabs\n" % path)
                return True

            elif line.rstrip('\r\n') != line.rstrip('\r\n '):
                ui.warn("file %s has trailing whitespace\n" % path)
                return True

    return False

def compare_revisions(repo, ui, rev1, rev2):
    """Given a known good revision 'rev1' and a revision 'rev2',
    check all files that have changed between 'rev1' and 'rev2'
    for whitespace issues.

    Returns a count of bad files.

    """
    bad_files = 0
    status = repo.status(rev1, rev2)
    modified, added = status[0], status[1]
    for path in modified + added:
        if check_file(ui, repo, path, rev2):
            bad_files += 1
    return bad_files

def check_whitespace(ui, repo, **kwargs):
    """Check whitespace for an incoming changegroup.

    Suitable for use as a pretxnchangegroup hook.

    """
    bad_files = 0

    # revision number of first incoming changeset of the changegroup
    first = repo[kwargs['node']].rev()

    # Process each head in range first:tip (inclusive) separately
    head_matcher = revset.match('heads(%d:)' % first)
    for head in head_matcher(repo, range(len(repo))):
        # Find the immediate pre-changegroup revisions that this head
        # descends from.
        source_pattern = ('(parents(%d:) - (%d:)) and ancestors(%d)' %
                          (first, first, head))
        source_matcher = revset.match(source_pattern)
        sources = list(source_matcher(repo, range(len(repo))))

        # Every revision already in the repo is assumed to be whitespace-clean,
        # so it's enough to pick just one 'sources' revision and check files
        # that have changed between that revision and 'head'.  (More generally,
        # we could check only those files that have changed since *every*
        # source revision, but it doesn't seem worth the extra effort involved
        # in computing the list of changed files.)
        if sources:
            source = sources[0]
        else:
            # Could happen on the first push to an empty repository.
            source = node.nullrev

        # Check all modified and/or added files between source and head.
        bad_files += compare_revisions(repo, ui, source, head)

    if bad_files:
        msg = ("run Tools/scripts/reindent.py on .py files or "
               "Tools/scripts/reindent-rst.py on .rst files listed above and\n"
               "rerun your tests to fix this before checking in\n")
        ui.warn(msg)
        # return value of 'True' indicates failure
        return True

def check_whitespace_single(ui, repo, **kwargs):
    """Check whitespace for a single changeset.

    Suitable for use as a pretxncommit hook.

    """
    head = repo[kwargs['node']].rev()
    # Enough to compare with just one parent:  both parents should
    # be whitespace-clean already.
    source = repo[kwargs['parent1']].rev()

    if compare_revisions(repo, ui, source, head):
        msg = ("run Tools/scripts/reindent.py on .py files or "
               "Tools/scripts/reindent-rst.py on .rst files listed above and\n"
               "rerun your tests to fix this before checking in\n")
        ui.warn(msg)
        # return value of 'True' indicates failure
        return True
