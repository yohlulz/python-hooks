"""
Mercurial hook to send an email for each changeset to a specified address.

For use as an "incoming" hook.

To set the SMTP server to something other than localhost, add a [smtp]
section to your hgrc:

[smtp]
host = mail.python.org
port = 25

"""

from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from mercurial import cmdutil, patch
from mercurial.node import nullid
from mercurial.encoding import fromlocal
from mercurial.util import iterlines
import smtplib
import os
import sys
import traceback

BASE = 'http://hg.python.org/'
CSET_URL = BASE + '%s/rev/%s'


def send(smtp, sub, sender, to, body):
    msg = MIMEMultipart()
    msg['Subject'] = Header(sub, 'utf8')
    msg['To'] = to
    msg['From'] = sender
    msg.attach(MIMEText(body, _subtype='plain', _charset='utf8'))
    smtp.sendmail(sender, to, msg.as_string())

def strip_bin_diffs(chunks):
    stripped = []
    for chunk in chunks:
        lines = chunk.splitlines(True)
        try:
            # This is the second or third line usually
            i = lines.index('GIT binary patch\n', 0, 4)
        except ValueError:
            pass
        else:
            lines = lines[:i+1] + ['[stripped]\n']
            chunk = ''.join(lines)
        stripped.append(chunk)
    return stripped

def strip_blacklisted_files(chunks, blacklisted):
    stripped = []
    for chunk in chunks:
        lines = chunk.splitlines(True)
        for i, line in enumerate(lines[:4]):
            if (line.startswith('+++ b/') and
                line[6:].rstrip() in blacklisted):
                lines = lines[:i+1] + ['[stripped]\n']
                chunk = ''.join(lines)
                break
        stripped.append(chunk)
    return stripped

def _incoming(ui, repo, **kwargs):
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

    blacklisted = ui.config('mail', 'diff-blacklist', '').split()

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
    body += ['summary:\n  ' + fromlocal(ctx.description())]
    # ctx.files() gives us misleading info on merges, we use a diffstat instead
    body += ['', 'files:']

    diffopts = patch.diffopts(repo.ui, {'git': True, 'showfunc': True})
    parents = ctx.parents()
    node1 = parents and parents[0].node() or nullid
    node2 = ctx.node()
    diffchunks = list(patch.diff(repo, node1, node2, opts=diffopts))
    diffstat = patch.diffstat(iterlines(diffchunks), width=60, git=True)
    for line in iterlines([''.join(diffstat)]):
        body.append(' ' + line)
    body += ['', '']
    diffchunks = strip_bin_diffs(diffchunks)
    diffchunks = strip_blacklisted_files(diffchunks, blacklisted)
    body.append(''.join(chunk for chunk in diffchunks))

    body.append('-- ')
    body.append('Repository URL: %s%s' % (BASE, path))

    to = ui.config('mail', 'notify', None)
    if to is None:
        print 'no email address configured'
        return False
    from_ = ui.config('mail', 'sender', None)
    if from_ is None:
        from_ = to
    sender = '%s <%s>' % (user, from_)

    prefixes = [path]

    if len(parents) == 2:
        b1, b2, b = parents[0].branch(), parents[1].branch(), ctx.branch()
        if b in (b1, b2):
            bp = b2 if b == b1 else b1
            # normal case
            prefixes.append('(merge %s -> %s)' % (bp, b))
        else:
            # XXX really??
            prefixes.append('(merge %s + %s -> %s)' % (b1, b2, b))
    else:
        branch = ctx.branch()
        if branch != 'default':
            prefixes.append('(%s)' % branch)

    desc = ctx.description().splitlines()[0]
    if len(desc) > 80:
        desc = desc[:80]
        if ' ' in desc:
            desc = desc.rsplit(' ', 1)[0]

    if prefixes:
        prefixes = ' '.join(prefixes) + ': '
    else:
        prefixes = ''

    subj = prefixes + desc

    host = ui.config('smtp', 'host', '')
    port = int(ui.config('smtp', 'port', 0))
    smtp = smtplib.SMTP(host, port)
    username = ui.config('smtp', 'username', '')
    if username:
        smtp.login(username, ui.config('smtp', 'password', ''))
    send(smtp, subj, sender, to, '\n'.join(body) + '\n')
    smtp.close()

    ui.status('notified %s of incoming changeset %s\n' % (to, ctx))
    return False

def incoming(ui, repo, **kwargs):
    # Make error reporting easier
    try:
        return _incoming(ui, repo, **kwargs)
    except:
        traceback.print_exc()
        raise

