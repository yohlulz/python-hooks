from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from mercurial import cmdutil, patch
from mercurial.node import nullid
import smtplib
import os

BASE = 'http://hg.python.org/'
CSET_URL = BASE + '%s/rev/%s'
FROM = '%s <python-checkins@python.org>'

# foo

def send(sub, sender, to, body):
    msg = MIMEMultipart()
    msg['Subject'] = sub
    msg['To'] = to
    msg['From'] = sender
    msg.attach(MIMEText(body, _subtype='plain'))
    smtp = smtplib.SMTP()
    smtp.connect()
    smtp.sendmail(sender, msg['To'], msg.as_string())
    smtp.close()

def incoming(ui, repo, **kwargs):

    displayer = cmdutil.changeset_printer(ui, repo, False, False, True)
    ctx = repo[kwargs['node']]
    displayer.show(ctx)
    log = displayer.hunk[ctx.rev()]
    user = os.environ.get('HGPUSHER', 'local')
    path = '/'.join(repo.root.split('/')[4:])

    body = ['%s pushed %s to %s:' % (user, str(ctx), path), '']
    body += [CSET_URL % (path, ctx)]
    body += log.splitlines()[:-2]
    body += ['summary:\n  ' + ctx.description(), '']
    body += ['files:\n  ' + '\n  '.join(ctx.files()), '']

    diffopts = patch.diffopts(repo.ui, {'git': True, 'showfunc': True})
    parents = ctx.parents()
    node1 = parents and parents[0].node() or nullid
    node2 = ctx.node()
    differ = patch.diff(repo, node1, node2, opts=diffopts)
    body.append(''.join(chunk for chunk in differ))

    body.append('--')
    body.append('Repository URL: %s%s' % (BASE, path))

    to = ui.config('mail', 'notify', None)
    if to is None:
        print 'no email address configured'
        return False

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
    if len(parents) > 1:
        subj = "merge in " + subj

    send(subj, FROM % user, to, '\n'.join(body))
    print 'notified %s of incoming changeset %s' % (to, ctx)
    return False
