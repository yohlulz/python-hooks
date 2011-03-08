"""Mercurial hook to update a Roundup issue.

Update a Roundup issue via email for changesets where commit messages
mention an issue anywhere in the commit message in the following way:

   #12345
   issue12345
   issue 12345
   bug12345
   bug 12345

where 12345 is the issue number.

If "closes" or "fixes" (with alternative verb forms like "fixing"
allowed too) is prepended, the issue is automatically closed as
"fixed".

To use this hook, include the following in hgrc:

    [hooks]
    changegroup.roundup = python:hgroundup.update_issue

    [hgroundup]
    repo = http://hg.python.org/cpython/rev/
    toaddr = roundup-admin@example.com
    mailrelay = 127.0.0.1

Initial implementation by Kelsey Hightower <kelsey.hightower@gmail.com>.
"""
import re
import smtplib
import posixpath
import traceback

from string import Template
from email.mime.text import MIMEText

from mercurial.templatefilters import person
from mercurial.encoding import fromlocal

VERBS = r'(?:\b(?P<verb>close[sd]?|closing|)\s+)?'
ISSUE_PATTERN = re.compile(r'%s(?:#|\bissue|\bbug)\s*(?P<issue_id>[0-9]{4,})'
                           % VERBS, re.I)
COMMENT_TEMPLATE = """\
New changeset ${changeset_id} by $author in branch '${branch}':
${commit_msg}
${changeset_url}
"""


def update_issue(*args, **kwargs):
    try:
        _update_issue(*args, **kwargs)
    except:
        traceback.print_exc()
        raise

def _update_issue(ui, repo, node, **kwargs):
    """Update a Roundup issue for corresponding changesets.

    Return True if updating the Roundup issue fails, else False.
    """
    repourl = ui.config('hgroundup', 'repourl')
    if not repourl:
        repourl = posixpath.join(ui.config('web', 'baseurl'), 'rev/')
    fromaddr = ui.config('hgroundup', 'fromaddr')
    toaddr = ui.config('hgroundup', 'toaddr')
    mailrelay = ui.config('hgroundup', 'mailrelay', default='127.0.0.1')
    for var in ('repourl', 'fromaddr', 'toaddr'):
        if not locals()[var]:
            raise RuntimeError(
                'roundup hook not configured properly,\nplease '
                'set the "%s" property in the [hgroundup] section'
                % var)
    start = repo[node].rev()

    issues = {}

    for rev in xrange(start, len(repo)):
        ctx = repo[rev]
        description = fromlocal(ctx.description().strip())
        match = ISSUE_PATTERN.search(description)
        ui.debug('match in commit msg: %s\n' % (match and match.groupdict() or 'no'))
        if not match:
            continue
        data = match.groupdict()
        comment = Template(COMMENT_TEMPLATE).substitute({
            'author': fromlocal(person(ctx.user())),
            'branch': ctx.branch(),
            'changeset_id': str(ctx),
            'changeset_url': posixpath.join(repourl, str(ctx)),
            'commit_msg': description.splitlines()[0],
        })
        add_comment(issues, data, comment)
    if issues:
        try:
            send_comments(mailrelay, fromaddr, toaddr, issues)
            ui.status("sent email to roundup at " + toaddr + '\n')
        except Exception, err:
            # make sure an issue updating roundup does not prevent an
            # otherwise successful push.
            ui.warn("sending email to roundup at %s failed: %s\n" %
                    (toaddr, err))
    else:
        ui.debug("no issues to send to roundup\n")
    return False

def add_comment(issues, data, comment):
    """Process a comment made in a commit message."""
    key = data['issue_id']
    if key in issues:
        issues[key]['comments'].append(comment)
    else:
        issues[key] = {'comments': [comment], 'properties': {}}
    if data['verb']:
        issues[key]['properties'].update({
            'status': 'closed',
            'resolution': 'fixed'
        })

def send_comments(mailrelay, fromaddr, toaddr, issues):
    """Update the Roundup issue with a comment and changeset link."""
    s = smtplib.SMTP(mailrelay)
    try:
        for issue_id, data in issues.iteritems():
            props = ''
            if data['properties']:
                props = ' [%s]' % ';'.join('%s=%s' % x
                                           for x in data['properties'].iteritems())
            msg = MIMEText('\n\n'.join(data['comments']),
                           _subtype='plain', _charset='utf8')
            msg['From'] = fromaddr
            msg['To'] = toaddr
            msg['Subject'] = "[issue%s]%s" % (issue_id, props)
            s.sendmail(fromaddr, toaddr, msg.as_string())
    finally:
        s.quit()
