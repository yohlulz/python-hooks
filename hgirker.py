from mercurial.node import bin, short
from mercurial.templatefilters import person
from mercurial import cmdutil, patch, templater, util, mail

import os
import json
import socket

IRKER_HOST = 'localhost'
IRKER_PORT = 6659

DEFTEMPLATE = '''%(bold)s%(project)s:%(bold)s \
%(green)s%(author)s%(reset)s \
%(yellow)s%(branch)s%(reset)s \
* %(bold)s%(rev)s%(bold)s \
/ %(files)s%(bold)s:%(bold)s %(logmsg)s \
%(gray)s%(url)s%(reset)s'''

def getenv(ui, repo):
    env = {
        'bold': '\x02',
        'green': '\x033',
        'blue': '\x032',
        'yellow': '\x037',
        'brown': '\x035',
        'gray': '\x0314',
        'reset': '\x0F'
    }
    env['repo'] = repo
    env['project'] = ui.config('irker', 'project')
    if env['project'] is None:
        raise RuntimeError('missing irker.project config value')
    env['baseurl'] = ui.config('web', 'baseurl')
    env['template'] = ui.config('irker', 'template', DEFTEMPLATE)
    env['channels'] = ui.config('irker', 'channels')
    if env['channels'] is None:
        raise RuntimeError('missing irker.channels config value')
    return env

def getfiles(env, ctx):
    f = env['repo'].status(ctx.p1().node(), ctx.node())
    elems = []
    for path in f[0] + f[1] + f[2]:
        elems.append(path)
    pfx = os.path.commonprefix(elems)
    if len(elems) > 1 and pfx:
        return pfx + '(' + ' '.join(e[len(pfx):] for e in elems) + ')'
    return ' '.join(elems)

def generate(env, ctx):
    n = ctx.node()
    ns = short(n)
    d = env.copy()
    d['branch'] = ctx.branch()
    d['author'] = person(ctx.user())
    d['rev'] = '%d:%s' % (ctx.rev(), ns)
    d['logmsg'] = ctx.description()
    if env['baseurl']:
        d['url'] = env['baseurl'].rstrip('/') + '/rev/%s' % ns
    else:
        d['url'] = ''
    d['files'] = getfiles(env, ctx)
    return json.dumps({
        'to': env['channels'].split(','),
        'privmsg': d['template'] % d,
    })

def hook(ui, repo, hooktype, node=None, url=None, **kwds):
    def sendmsg(msg):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.connect((IRKER_HOST, IRKER_PORT))
            sock.sendall(msg + "\n")
        finally:
            sock.close()

    env = getenv(ui, repo)

    n = bin(node)
    if hooktype == 'changegroup':
        start = repo.changelog.rev(n)
        end = len(repo.changelog)
        for rev in xrange(start, end):
            n = repo.changelog.node(rev)
            ctx = repo.changectx(n)
            sendmsg(generate(env, ctx))
    else:
        ctx = repo.changectx(n)
        sendmsg(generate(env, ctx))
