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

def incoming(ui, repo, **kwargs):
	
	displayer = cmdutil.changeset_printer(ui, repo, False, False, True)
	ctx = repo[kwargs['node']]
	displayer.show(ctx)
	log = displayer.hunk[ctx.rev()]
	user = os.environ.get('HGPUSHER', 'local')
	path = '/'.join(repo.root.split('/')[4:])
	
	body = ['%s pushed %s to %s:' % (user, str(ctx), path), '']
	body += [CSET_URL % (path, ctx)]
	body += log.splitlines()
	body.append('--')
	body.append('Repository URL: %s%s' % (BASE, path))

	to = ui.config('mail', 'notify', None)
	if to is None:
		print 'no email address configured'
		return
	
	desc = ctx.description().splitlines()[0]
	if len(desc) > 80:
		desc = desc[:80]
		if ' ' in desc:
			desc = desc.rsplit(' ', 1)[0]
	
	subj = '%s in %s: %s' % (ctx, path, desc)
	send(subj, FROM % user, to, '\n'.join(body))
	print 'notified %s of incoming changeset %s' % (to, ctx)
