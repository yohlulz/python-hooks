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
    repo = http://hg.python.org/cpython/
    toaddr = roundup-admin@example.com
    mailrelay = 127.0.0.1
"""
import re
import smtplib
import posixpath

from string import Template
from email.mime.text import MIMEText

VERBS = r'(?:\b(?P<verb>close[sd]?|closing|fixe[sd]|fixing|fix)\s+)?'
ISSUE_PATTERN = re.compile(r'%s(?:#|\bissue|\bbug)\s*(?P<issue_id>[0-9]+)'
                           % VERBS, re.I)
COMMENT_TEMPLATE = "${commit_msg}\n${changeset_url}"


def update_issue(ui, repo, node, **kwargs):
    """Update a Roundup issue for corresponding changesets.

    Return True if updating the Roundup issue fails, else False.
    """
    repo_url = ui.config('hgroundup', 'repo')
    toaddr = ui.config('hgroundup', 'toaddr')
    mailrelay = ui.config('hgroundup', 'mailrelay', default='127.0.0.1')
    start = repo[node].rev()

    issues = {}

    for rev in xrange(start, len(repo)):
        ctx = repo[rev]
        description = ctx.description()
        match = ISSUE_PATTERN.search(description)
        ui.warn('match in commit msg: %s\n' % (match and match.groupdict() or 'no'))
        if not match:
            continue
        data = match.groupdict()
        comment = Template(COMMENT_TEMPLATE).substitute({
            'changeset_url': posixpath.join(repo_url, str(ctx)),
            'commit_msg': description,
        })
        add_comment(issues, ctx.user(), data, comment)
    if issues:
        try:
            send_comments(mailrelay, toaddr, issues)
            ui.status("Sent email to roundup at " + toaddr + '\n')
        except Exception, err:
            # make sure an issue updating roundup does not prevent an
            # otherwise successful push.
            ui.warn("Sending email to roundup at %s failed: %s\n" %
                    (toaddr, err))
    else:
        ui.debug("No issues to send to roundup\n")
    return False

def add_comment(issues, user, data, comment):
    """Process a comment made in a commit message."""
    key = (data['issue_id'], user)
    if key in issues:
        issues[key]['comments'].append(comment)
    else:
        issues[key] = {'comments': [comment], 'properties': {}}
    if data['verb']:
        issues[key]['properties'].update({
            'status': 'closed',
            'resolution': 'fixed'
        })

def send_comments(mailrelay, toaddr, issues):
    """Update the Roundup issue with a comment and changeset link."""
    for (issue_id, user), data in issues.iteritems():
        props = ''
        if data['properties']:
            props = ' [%s]' % ';'.join('%s=%s' % x
                                       for x in data['properties'].iteritems())
        msg = MIMEText('\n\n'.join(data['comments']))
        msg['From'] = user
        msg['To'] = toaddr
        msg['Subject'] = "[issue%s]%s" % (issue_id, props)
        import sys
        print >>sys.stderr, msg['Subject']
        s = smtplib.SMTP(mailrelay)
        s.sendmail(user, toaddr, msg.as_string())
        s.quit()
