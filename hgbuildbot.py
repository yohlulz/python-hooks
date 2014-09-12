# buildbot.py - mercurial changegroup hook for buildbot
#
# Copyright 2007 Frederic Leroy <fredo@starox.org>
# Adapted for Python 2010 Georg Brandl <georg@python.org>
#
# This software may be used and distributed according to the terms
# of the GNU General Public License, incorporated herein by reference.

# hook extension to send change notifications to buildbot when a changeset is
# brought into the repository from elsewhere.
#
# to use, configure hgbuildbot in .hg/hgrc like this:
#
#   [hooks]
#   changegroup.buildbot = python:/path/to/buildbot.py:hook
#
#   [hgbuildbot]
#   master = host1:port1,host2:port2,...
#   prefix = python/   # optional!

import os
import sys
from cStringIO import StringIO

from mercurial.i18n import gettext as _
from mercurial.node import bin, hex, nullid
from mercurial.context import workingctx
from mercurial.encoding import localstr, fromlocal

# mercurial's on-demand-importing hacks interfere with the:
#from zope.interface import Interface
# that Twisted needs to do, so disable it.
try:
    from mercurial import demandimport
    demandimport.disable()
except ImportError:
    pass

from twisted.internet import defer, reactor

sys.path.append('/data/buildbot/lib/python')


def sendchanges(ui, master, changes):
    # send change information to one master
    from buildbot.clients import sendchange

    s = sendchange.Sender(master)
    d = defer.Deferred()
    reactor.callLater(0, d.callback, None)

    def send(res, c):
        return s.send(**c)
    for change in changes:
        for k, v in change.items():
            # Yikes!
            if isinstance(v, localstr):
                change[k] = fromlocal(v).decode('utf8', 'replace')
            elif isinstance(v, str):
                change[k] = v.decode('utf8', 'replace')
        d.addCallback(send, change)

    def printSuccess(res):
        print "change(s) sent successfully"

    def printFailure(why):
        print "change(s) NOT sent, something went wrong:"
        print why

    d.addCallbacks(printSuccess, printFailure)
    d.addBoth(lambda _: reactor.stop())


def hook(ui, repo, hooktype, node=None, source=None, **kwargs):
    # read config parameters
    masters = ui.configlist('hgbuildbot', 'master')
    if not masters:
        ui.write("* You must add a [hgbuildbot] section to .hg/hgrc in "
                 "order to use buildbot hook\n")
        return
    prefix = ui.config('hgbuildbot', 'prefix', '')
    url = ui.config('hgbuildbot', 'rev_url', '')

    if hooktype != 'changegroup':
        ui.status('hgbuildbot: hook %s not supported\n' % hooktype)
        return

    # find changesets and collect info
    changes = []
    start = repo[node].rev()
    end = len(repo)
    for rev in xrange(start, end):
        # read changeset
        node = repo.changelog.node(rev)
        manifest, user, (time, timezone), files, desc, extra = repo.changelog.read(node)
        parents = [p for p in repo.changelog.parents(node) if p != nullid]
        branch = extra['branch']
        if branch in ['2.5', '2.6']:
            # No buildbot category for these branches
            continue
        if len(parents) > 1:
            # Explicitly compare current with its first parent (otherwise
            # some files might be "forgotten" if they are copied as-is from the
            # second parent).
            p1 = repo[hex(parents[0])]
            modified, added, removed, deleted = repo.status(rev, p1)[:4]
            files = set()
            for l in (modified, added, removed, deleted):
                files.update(l)
            files = sorted(files)
            if not files:
                # dummy merge, but at least one file is required by buildbot
                files.append("Misc/merge")
        # add artificial prefix if configured
        files = [prefix + f for f in files]
        changes.append({
            'who': user,
            'revision': hex(node),
            'comments': desc,
            'revlink': (url % {'rev': hex(node)}) if url else '',
            'files': files,
            'branch': branch,
        })

    old_stdout = sys.stdout
    new_stdout = sys.stdout = StringIO()
    try:
        for master in masters:
            sendchanges(ui, master, changes)
        reactor.run()
    finally:
        sys.stdout = old_stdout
        new_stdout.seek(0)
        for s in new_stdout:
            ui.status("buildbot: " + s)

