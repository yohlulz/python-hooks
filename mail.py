"""
Mercurial hook to send an email for each changeset to a specified address.

For use as an "incoming" hook.
"""

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from mercurial import cmdutil, patch
from mercurial.node import nullid
from mercurial.encoding import fromlocal
import smtplib
import os
import sys

BASE = 'http://hg.python.org/'
CSET_URL = BASE + '%s/rev/%s'
FROM = '%s <python-checkins@python.org>'

def send(sub, sender, to, body):
    msg = MIMEMultipart()
    msg['Subject'] = sub
    msg['To'] = to
    msg['From'] = sender
    msg.attach(MIMEText(body, _subtype='plain', _charset='utf8'))
    smtp = smtplib.SMTP()
    smtp.connect()
    smtp.sendmail(sender, msg['To'], msg.as_string())
    smtp.close()

def incoming(ui, repo, **kwargs):
    # Ensure that no fancying of output is enabled (e.g. coloring)
    os.environ['TERM'] = 'dumb'
    ui.setconfig('ui', 'interactive', 'False')
    ui.setconfig('ui', 'formatted', 'False')
    try:
        colormod = sys.modules['hgext.color']
    except KeyError:
        pass
    else:
        colormod._styles.clear()

    displayer = cmdutil.changeset_printer(ui, repo, False, False, True)
    ctx = repo[kwargs['node']]
    displayer.show(ctx)
    log = displayer.hunk[ctx.rev()]
    user = os.environ.get('HGPUSHER', 'local')
    path = '/'.join(repo.root.split('/')[4:])

    body = []
    #body += ['%s pushed %s to %s:' % (user, str(ctx), path), '']
    body += [CSET_URL % (path, ctx)]
    body += [line for line in log.splitlines()[:-2]
             if line != 'tag:         tip']
    body += ['summary:\n  ' + fromlocal(ctx.description()), '']
    body += ['files:\n  ' + '\n  '.join(ctx.files()), '']

    diffopts = patch.diffopts(repo.ui, {'git': True, 'showfunc': True})
    parents = ctx.parents()
    node1 = parents and parents[0].node() or nullid
    node2 = ctx.node()
    differ = patch.diff(repo, node1, node2, opts=diffopts)
    body.append(''.join(chunk for chunk in differ))

    body.append('-- ')
    body.append('Repository URL: %s%s' % (BASE, path))

    to = ui.config('mail', 'notify', None)
    if to is None:
        print 'no email address configured'
        return False

    if len(parents) == 2:
        b1, b2, b = parents[0].branch(), parents[1].branch(), ctx.branch()
        if b in (b1, b2):
            bp = b2 if b == b1 else b1
            # normal case
            branch_insert = ' (merge %s -> %s)' % (bp, b)
        else:
            # XXX really??
            branch_insert = ' (merge %s + %s -> %s)' % (b1, b2, b)
    else:
        branch = ctx.branch()
        if branch == 'default':
            branch_insert = ''
        else:
            branch_insert = ' (%s)' % branch

    desc = ctx.description().splitlines()[0]
    if len(desc) > 80:
        desc = desc[:80]
        if ' ' in desc:
            desc = desc.rsplit(' ', 1)[0]

    subj = '%s%s: %s' % (path, branch_insert, desc)

    send(subj, FROM % user, to, '\n'.join(body) + '\n')
    print 'notified %s of incoming changeset %s' % (to, ctx)
    return False

