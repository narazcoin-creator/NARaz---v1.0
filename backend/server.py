import hashlib, json, os, secrets, sqlite3, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

DB_PATH = os.environ.get('NARAZ_DB', os.path.join(os.path.dirname(__file__), 'naraz.db'))
HOST = os.environ.get('NARAZ_HOST', '0.0.0.0')
PORT = int(os.environ.get('NARAZ_PORT', '8080'))
TOKEN = 'NARaz'
MAX_SUPPLY = 1_000_000_000
TESTNET_GRANT = 1_000.0


def db():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def now(): return time.time()


def hash_password(password, salt=None):
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 180_000)
    return salt.hex() + '$' + digest.hex()


def verify_password(password, stored):
    try:
        salt_hex, digest_hex = stored.split('$', 1)
        digest = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt_hex), 180_000)
        return secrets.compare_digest(digest.hex(), digest_hex)
    except Exception:
        return False


def wallet_address():
    return 'NAR1' + secrets.token_hex(20)


def init_db():
    c = db()
    c.executescript('''
    CREATE TABLE IF NOT EXISTS users (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      username TEXT NOT NULL UNIQUE COLLATE NOCASE,
      email TEXT NOT NULL UNIQUE COLLATE NOCASE,
      password_hash TEXT NOT NULL,
      wallet TEXT NOT NULL UNIQUE,
      created_at REAL NOT NULL
    );
    CREATE TABLE IF NOT EXISTS sessions (
      token TEXT PRIMARY KEY,
      user_id INTEGER NOT NULL,
      created_at REAL NOT NULL,
      FOREIGN KEY(user_id) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS blocks (
      idx INTEGER PRIMARY KEY,
      timestamp REAL NOT NULL,
      transactions TEXT NOT NULL,
      previous_hash TEXT NOT NULL,
      nonce INTEGER NOT NULL,
      hash TEXT NOT NULL UNIQUE
    );
    CREATE TABLE IF NOT EXISTS pending (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      sender TEXT NOT NULL,
      recipient TEXT NOT NULL,
      amount REAL NOT NULL,
      timestamp REAL NOT NULL,
      tx_id TEXT NOT NULL UNIQUE
    );
    ''')
    if c.execute('SELECT COUNT(*) n FROM blocks').fetchone()['n'] == 0:
        genesis = {
            'index': 0,
            'timestamp': now(),
            'transactions': [{'id':'GENESIS','sender':'SYSTEM','recipient':'TESTNET_FAUCET','amount':MAX_SUPPLY}],
            'previous_hash': '0',
            'nonce': 0,
        }
        genesis['hash'] = block_hash(genesis)
        c.execute('INSERT INTO blocks VALUES (?,?,?,?,?,?)', (0, genesis['timestamp'], json.dumps(genesis['transactions']), '0', 0, genesis['hash']))
    c.commit(); c.close()


def block_hash(b):
    raw = json.dumps({k:b[k] for k in ['index','timestamp','transactions','previous_hash','nonce']}, sort_keys=True, separators=(',', ':')).encode()
    return hashlib.sha256(raw).hexdigest()


def chain_rows(c):
    return c.execute('SELECT * FROM blocks ORDER BY idx').fetchall()


def balance(c, address):
    total = 0.0
    for r in chain_rows(c):
        for tx in json.loads(r['transactions']):
            if tx['sender'] == address: total -= float(tx['amount'])
            if tx['recipient'] == address: total += float(tx['amount'])
    for r in c.execute('SELECT sender,recipient,amount FROM pending'):
        if r['sender'] == address: total -= float(r['amount'])
        if r['recipient'] == address: total += float(r['amount'])
    return round(total, 8)


def supply(c):
    total = 0.0
    for r in chain_rows(c):
        for tx in json.loads(r['transactions']):
            if tx['sender'] == 'SYSTEM': total += float(tx['amount'])
    return round(total, 8)


def make_tx(sender, recipient, amount):
    return {'id': secrets.token_hex(16), 'sender':sender, 'recipient':recipient, 'amount':float(amount), 'timestamp':now()}


def mine_pending(c):
    rows = c.execute('SELECT * FROM pending ORDER BY id').fetchall()
    if not rows: return None
    txs = [dict(id=r['tx_id'], sender=r['sender'], recipient=r['recipient'], amount=r['amount'], timestamp=r['timestamp']) for r in rows]
    idx = c.execute('SELECT MAX(idx) m FROM blocks').fetchone()['m'] + 1
    prev = c.execute('SELECT hash FROM blocks WHERE idx=?', (idx-1,)).fetchone()['hash']
    b = {'index':idx,'timestamp':now(),'transactions':txs,'previous_hash':prev,'nonce':0}
    b['hash'] = block_hash(b)
    c.execute('INSERT INTO blocks VALUES (?,?,?,?,?,?)', (idx,b['timestamp'],json.dumps(txs),prev,0,b['hash']))
    c.execute('DELETE FROM pending')
    c.commit(); return b


def auth_user(c, headers):
    token = headers.get('Authorization','')
    if not token.startswith('Bearer '): return None
    row = c.execute('SELECT u.* FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token=?', (token[7:].strip(),)).fetchone()
    return row


def body(h):
    n = int(h.headers.get('Content-Length','0'))
    try: return json.loads(h.rfile.read(n) or b'{}')
    except json.JSONDecodeError: raise ValueError('Invalid JSON')


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args): return
    def out(self, data, status=200):
        raw=json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_header('Access-Control-Allow-Origin','*'); self.send_header('Access-Control-Allow-Headers','Content-Type, Authorization'); self.send_header('Access-Control-Allow-Methods','GET,POST,OPTIONS'); self.send_header('Content-Length',str(len(raw))); self.end_headers(); self.wfile.write(raw)
    def do_OPTIONS(self): self.out({},204)
    def do_GET(self):
        c=db(); p=urlparse(self.path).path
        try:
            if p == '/api/network':
                return self.out({'network':'NARaz Network','token':TOKEN,'max_supply':MAX_SUPPLY,'supply':supply(c),'chain_length':c.execute('SELECT COUNT(*) n FROM blocks').fetchone()['n'],'online':True})
            if p == '/api/chain':
                blocks=[]
                for r in chain_rows(c): blocks.append({'index':r['idx'],'timestamp':r['timestamp'],'transactions':json.loads(r['transactions']),'previous_hash':r['previous_hash'],'nonce':r['nonce'],'hash':r['hash']})
                return self.out({'chain':blocks})
            if p == '/api/me':
                u=auth_user(c,self.headers)
                if not u:return self.out({'error':'Unauthorized'},401)
                return self.out({'username':u['username'],'email':u['email'],'wallet':u['wallet'],'balance':balance(c,u['wallet']),'token':TOKEN})
            if p.startswith('/api/balance/'):
                a=p.split('/api/balance/',1)[1]; return self.out({'address':a,'balance':balance(c,a),'token':TOKEN})
            if p == '/api/transactions':
                u=auth_user(c,self.headers)
                if not u:return self.out({'error':'Unauthorized'},401)
                wallet=u['wallet']; out=[]
                for r in chain_rows(c):
                    for tx in json.loads(r['transactions']):
                        if tx['sender']==wallet or tx['recipient']==wallet: out.append(tx)
                return self.out({'transactions':out[-100:][::-1]})
            return self.out({'error':'Not found'},404)
        finally: c.close()
    def do_POST(self):
        c=db(); p=urlparse(self.path).path
        try:
            data=body(self)
            if p == '/api/register':
                username=str(data.get('username','')).strip(); email=str(data.get('email','')).strip().lower(); password=str(data.get('password',''))
                if len(username)<3 or len(username)>32:return self.out({'error':'Username must be 3-32 characters'},400)
                if len(password)<8:return self.out({'error':'Password must be at least 8 characters'},400)
                if '@' not in email:return self.out({'error':'Valid email required'},400)
                if c.execute('SELECT 1 FROM users WHERE username=? COLLATE NOCASE',(username,)).fetchone(): return self.out({'error':'Username already exists'},409)
                if c.execute('SELECT 1 FROM users WHERE email=? COLLATE NOCASE',(email,)).fetchone(): return self.out({'error':'Email already exists'},409)
                wallet=wallet_address(); c.execute('INSERT INTO users(username,email,password_hash,wallet,created_at) VALUES(?,?,?,?,?)',(username,email,hash_password(password),wallet,now()))
                user_id=c.execute('SELECT last_insert_rowid() id').fetchone()['id']
                tx=make_tx('TESTNET_FAUCET',wallet,TESTNET_GRANT); c.execute('INSERT INTO pending(sender,recipient,amount,timestamp,tx_id) VALUES(?,?,?,?,?)',(tx['sender'],tx['recipient'],tx['amount'],tx['timestamp'],tx['id']))
                mine_pending(c)
                token=secrets.token_urlsafe(32); c.execute('INSERT INTO sessions VALUES(?,?,?)',(token,user_id,now())); c.commit()
                return self.out({'message':'Account created','token':token,'user':{'username':username,'email':email,'wallet':wallet,'balance':balance(c,wallet),'token_name':TOKEN}},201)
            if p == '/api/login':
                email=str(data.get('email','')).strip().lower(); password=str(data.get('password',''))
                u=c.execute('SELECT * FROM users WHERE email=? COLLATE NOCASE',(email,)).fetchone()
                if not u or not verify_password(password,u['password_hash']): return self.out({'error':'Invalid email or password'},401)
                token=secrets.token_urlsafe(32); c.execute('INSERT INTO sessions VALUES(?,?,?)',(token,u['id'],now())); c.commit(); return self.out({'token':token,'user':{'username':u['username'],'email':u['email'],'wallet':u['wallet'],'balance':balance(c,u['wallet']),'token_name':TOKEN}})
            u=auth_user(c,self.headers)
            if not u:return self.out({'error':'Unauthorized'},401)
            if p == '/api/transfer':
                recipient=str(data.get('recipient','')).strip(); amount=float(data.get('amount',0))
                if amount<=0:return self.out({'error':'Amount must be positive'},400)
                dest=c.execute('SELECT wallet,username FROM users WHERE wallet=? OR username=? COLLATE NOCASE',(recipient,recipient)).fetchone()
                if not dest:return self.out({'error':'Recipient not found'},404)
                if dest['wallet']==u['wallet']:return self.out({'error':'Cannot send to yourself'},400)
                if amount>balance(c,u['wallet']):return self.out({'error':'Insufficient balance'},400)
                tx=make_tx(u['wallet'],dest['wallet'],amount); c.execute('INSERT INTO pending(sender,recipient,amount,timestamp,tx_id) VALUES(?,?,?,?,?)',(tx['sender'],tx['recipient'],tx['amount'],tx['timestamp'],tx['id']))
                block=mine_pending(c)
                return self.out({'message':'Transfer confirmed','transaction':tx,'block':block,'sender_balance':balance(c,u['wallet']),'recipient_balance':balance(c,dest['wallet'])},201)
            return self.out({'error':'Not found'},404)
        except (ValueError,KeyError) as e:
            return self.out({'error':str(e)},400)
        finally: c.close()


if __name__=='__main__':
    init_db(); print(f'NARaz Network API listening on http://{HOST}:{PORT}'); ThreadingHTTPServer((HOST,PORT),Handler).serve_forever()
