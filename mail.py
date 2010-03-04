from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from mercurial import cmdutil
import smtplib
import os

BASE = 'http://hg.python.org/'
CSET_URL = BASE + '%s/rev/%s'
FROM = '%s <hg@python.org>'

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

def changegroup(ui, repo, **kwargs):
	
	displayer = cmdutil.changeset_printer(ui, repo, False, False, True)
	first = repo[kwargs['node']].rev()
	for i in range(first, len(repo)):
		displayer.show(repo[i])
	
	num = len(displayer.hunk)
	user = os.environ.get('HGPUSHER', 'local')
	path = '/'.join(repo.root.split('/')[4:])
	
	csets = ('%s new ' % num) + ('changesets' if num > 1 else 'changeset')
	body = ['%s pushed %s to %s:' % (user, csets, path), '']
	for rev, log in sorted(displayer.hunk.iteritems()):
		lines = log.splitlines()
		short = lines[0].rsplit(':', 1)[1]
		url = CSET_URL % (path, short)
		body.append(url)
		body += lines
		body.append('')
	
	body.append('--')
	body.append('Repository URL: %s%s' % (BASE, path))
	to = ui.config('mail', 'notify', None)
	if to is None:
		print 'no email address configured'
		return
	
	send(csets + ' in %s' % path, FROM % user, to, '\n'.join(body))
	print 'notified %s of %s' % (to, csets)
