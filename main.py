import os, re, html, time, logging, sqlite3, json
from decimal import Decimal, InvalidOperation
from urllib.parse import quote
import requests
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

BOT_TOKEN="8880814668:AAEfAa9aEzTHyNG5a6GWTByWJvivNbi2JZw"
ADMIN_CHAT_ID=8523301132
VERIFY_HANDLE="@srshihab69"
VERIFY_LINK="https://t.me/srshihab69"
POLL_TIMEOUT=50
DB_FILE="bot.db"

class DB:
    def conn(self):
        c=sqlite3.connect(DB_FILE, timeout=30)
        c.row_factory=sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA foreign_keys=ON")
        return c
    def execute(self, sql, args=(), fetch=False, one=False):
        # Convert the old MySQL placeholder style to SQLite.
        sql=sql.replace('%s','?')
        c=self.conn()
        try:
            cur=c.execute(sql,args)
            if fetch:
                rows=cur.fetchall()
                if one:
                    return dict(rows[0]) if rows else None
                return [dict(x) for x in rows]
            last=cur.lastrowid
            c.commit()
            return last
        finally:
            c.close()
    def ensure(self):
        c=self.conn()
        try:
            c.executescript("""
            CREATE TABLE IF NOT EXISTS py_states (
                telegram_id INTEGER PRIMARY KEY, state TEXT, data TEXT, updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY, value TEXT
            );
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT, telegram_id INTEGER UNIQUE NOT NULL,
                first_name TEXT DEFAULT 'User', email TEXT, otp_hash TEXT, otp_expires_at TEXT,
                state TEXT DEFAULT 'home', verified INTEGER DEFAULT 0, balance REAL DEFAULT 0,
                pending_balance REAL DEFAULT 0, language TEXT DEFAULT 'bn', referred_by INTEGER NULL,
                referral_bonus_awarded INTEGER DEFAULT 0, created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, logo TEXT, description TEXT,
                reward REAL DEFAULT 0, today_password TEXT, details TEXT, active INTEGER DEFAULT 1,
                task_image TEXT, logo_file_id TEXT, task_image_file_id TEXT, task_icon TEXT DEFAULT '📌',
                alert_text TEXT, submit_prompt1 TEXT, submit_prompt2 TEXT, submit_button_text TEXT,
                copy_button_text TEXT, password_label TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT, telegram_id INTEGER NOT NULL, category_id INTEGER NOT NULL,
                category_name TEXT, account_number TEXT, proof TEXT, reward REAL DEFAULT 0,
                status TEXT DEFAULT 'pending', admin_note TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS withdrawals (
                id INTEGER PRIMARY KEY AUTOINCREMENT, telegram_id INTEGER NOT NULL, amount REAL NOT NULL,
                method TEXT, account TEXT, status TEXT DEFAULT 'pending', admin_note TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT
            );
            """)
            defaults={
                'site_title':'Mango Cash','withdraw_min':'10','withdraw_methods':'bKash,Nagad,Binance',
                'referral_enabled':'1','referral_bonus':'1.00','auto_delete_enabled':'0','auto_delete_keep':'2',
                'support_text':'@yourusername','tutorial_text':'🎬 Tutorial',
                'welcome_text':'👋 <b>স্বাগতম!</b>\n\n🔐 <b>Verification Required</b>\n\nনিচের Open Link বাটনে গিয়ে Handle সংগ্রহ করুন, তারপর Verify Handle চাপুন।',
                'welcome_image':'','verify_handle':VERIFY_HANDLE,'verify_link':VERIFY_LINK,
                'alert_text':'⚠️ <b>গুরুত্বপূর্ণ:</b> কাজ শুরু করার আগে আজকের Password কপি করে নির্দেশনা অনুযায়ী কাজ করুন।',
                'pending_alert':'⏳ <b>আপনার কাজ Pending আছে!</b>\n\nAdmin Manual Verification করছে.',
                'design_home_title':'💰 Home','design_home_text':'💰 Balance: <b>{{balance}}</b>\n⏳ Pending: <b>{{pending}}</b>',
                'design_home_image':'','design_tasks_title':'💼 Available Tasks','design_tasks_text':'একটি কাজ নির্বাচন করুন।','design_tasks_image':'',
                'design_history_title':'📜 History','design_history_text':'আপনার কাজের History নিচে দেখুন।','design_history_image':'',
                'design_leaderboard_title':'🏆 Leaderboard','design_leaderboard_text':'সেরা Earners-দের তালিকা।','design_leaderboard_image':'',
                'design_referral_title':'🔗 Referral','design_referral_text':'বন্ধু Invite করে Bonus পান।','design_referral_image':'',
                'design_myref_title':'👥 My Ref','design_myref_text':'আপনার Referral List।','design_myref_image':'',
                'design_withdraw_title':'💸 Withdraw','design_withdraw_text':'আপনার Balance Withdraw করুন।','design_withdraw_image':'',
                'design_support_title':'🎧 Support','design_support_text':'প্রয়োজনে Support-এ যোগাযোগ করুন।','design_support_image':'',
                'design_tutorial_title':'🎬 Tutorial','design_tutorial_text':'Bot ব্যবহার করার Tutorial।','design_tutorial_image':'',
                'design_language_title':'🌐 Language','design_language_text':'আপনার ভাষা নির্বাচন করুন।','design_language_image':'',
                'design_welcome_title':'👋 Welcome','design_welcome_text':'','design_welcome_image':''
            }
            for k,v in defaults.items():
                c.execute("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)",(k,v))
            c.commit()
        finally:
            c.close()

db=DB(); db.ensure()

def esc(s): return html.escape(str(s or ''), quote=True)
def setting(k,d=''):
    r=db.execute('SELECT value FROM settings WHERE `key`=%s',(k,),True,True); return d if not r else (r['value'] if r['value'] is not None else d)
def set_setting(k,v): db.execute('INSERT INTO settings(`key`,`value`) VALUES(%s,%s) ON CONFLICT(`key`) DO UPDATE SET value=excluded.value',(k,v))
def api(method, **data):
    r=requests.post(f'https://api.telegram.org/bot{BOT_TOKEN}/{method}',data=data,timeout=65)
    return r.json()
def markup(rows, resize=False): return {'keyboard':rows,'resize_keyboard':True} if resize else {'inline_keyboard':rows}
def send(chat,text, kb=None):
    d={'chat_id':chat,'text':text,'parse_mode':'HTML','disable_web_page_preview':True}
    if kb: d['reply_markup']=__import__('json').dumps(kb,ensure_ascii=False)
    return api('sendMessage',**d)
def photo(chat,p,caption,kb=None):
    d={'chat_id':chat,'photo':p,'caption':caption,'parse_mode':'HTML'}
    if kb:d['reply_markup']=__import__('json').dumps(kb,ensure_ascii=False)
    return api('sendPhoto',**d)
def answer(cid,text=''): return api('answerCallbackQuery',callback_query_id=cid,text=text)

def user(cid, first='User'):
    r=db.execute('SELECT * FROM users WHERE telegram_id=%s',(cid,),True,True)
    if not r:
        db.execute('INSERT INTO users(telegram_id,first_name) VALUES(%s,%s)',(cid,first)); r=db.execute('SELECT * FROM users WHERE telegram_id=%s',(cid,),True,True)
    elif first and r['first_name']!=first: db.execute('UPDATE users SET first_name=%s WHERE telegram_id=%s',(first,cid)); r['first_name']=first
    return r

def setstate(cid,state,data=''):
    db.execute("INSERT INTO py_states(telegram_id,state,data) VALUES(%s,%s,%s) ON CONFLICT(telegram_id) DO UPDATE SET state=excluded.state,data=excluded.data,updated_at=CURRENT_TIMESTAMP",(cid,state,data))
    db.execute('UPDATE users SET state=%s WHERE telegram_id=%s',(state,cid))
def state(cid):
    r=db.execute('SELECT state,data FROM py_states WHERE telegram_id=%s',(cid,),True,True); return (r['state'],r['data']) if r else ('home','')

def main_kb():
    return markup([[{'text':'🏠 Home'}]])

def keyboard(lang='bn'):
    if lang=='en': rows=[['🏠 Home','💼 Work'],['📜 History','🏆 Leaderboard'],['🎧 Support','🔗 Referral'],['👥 My Ref','💸 Withdraw'],['🎬 Tutorial'],['🌐 Language']]
    else: rows=[['🏠 Home','💼 কাজ করুন'],['📜 History','🏆 Leaderboard'],['🎧 Support','🔗 Referral'],['👥 My Ref','💸 Withdraw'],['🎬 Tutorial'],['🌐 Language']]
    return markup(rows,True)

def design_value(key, fallback=''):
    return setting('design_'+key, fallback)

def render_feature(cid, feature, fallback_title, fallback_text, kb=None):
    u=user(cid)
    title=design_value(feature+'_title', fallback_title)
    text=design_value(feature+'_text', fallback_text)
    text=text.replace('{{name}}',esc(u['first_name'])).replace('{{balance}}',f"{float(u['balance']):.2f}").replace('{{pending}}',f"{float(u['pending_balance']):.2f}")
    img=design_value(feature+'_image','')
    body=f"<b>{esc(title)}</b>\n\n{text}" if title else text
    if img:
        r=photo(cid,img,body,kb)
        if r.get('ok'): return
    send(cid,body,kb)

def home(cid):
    u=user(cid)
    # Legacy home_image/home_text remain supported for compatibility.
    text=setting('home_text','') or design_value('home_text','💰 Balance: <b>{{balance}}</b>\n⏳ Pending: <b>{{pending}}</b>')
    text=text.replace('{{name}}',esc(u['first_name'])).replace('{{balance}}',f"{float(u['balance']):.2f}").replace('{{pending}}',f"{float(u['pending_balance']):.2f}")
    media=setting('home_file_id') or setting('home_image') or design_value('home_image','')
    body=text
    if media:
        r=photo(cid,media,body,keyboard(u['language']));
        if r.get('ok'): return
    send(cid,body,keyboard(u['language']))

def verify_start(cid):
    kb=markup([[{'text':'🔗 Open Link','url':setting('verify_link',VERIFY_LINK)}],[{'text':'✅ Verify Handle','callback_data':'start_verify'}]])
    msg=setting('welcome_text') or design_value('welcome_text','👋 <b>স্বাগতম!</b>')
    img=setting('welcome_image') or design_value('welcome_image','')
    if img and photo(cid,img,msg,kb).get('ok'): return
    send(cid,msg,kb)

def task(cid,tid):
    c=db.execute('SELECT * FROM categories WHERE id=%s AND active=1',(tid,),True,True)
    if not c:return
    L=user(cid)['language']; kb=markup([[{'text':c['password_label'] or ('🔐 Today Password' if L=='en' else '🔐 আজকের Password'),'callback_data':f'pass:{tid}'}],[{'text':'📖 Details','callback_data':f'details:{tid}'}],[{'text':c['submit_button_text'] or ('📤 Submit Job' if L=='en' else '📤 Submit Job'),'callback_data':f'submit:{tid}'}],[{'text':'⬅️ Back','callback_data':'tasks'}]])
    p=c.get('task_image_file_id') or c.get('task_image')
    l=c.get('logo_file_id') or c.get('logo')
    if p and photo(cid,p,esc(c['name']),kb).get('ok'):
        if l and l!=p: photo(cid,l,'')
        return
    if l and photo(cid,l,esc(c['name']),kb).get('ok'): return
    send(cid,esc(c['name']),kb)

def tasks(cid):
    cs=db.execute('SELECT * FROM categories WHERE active=1 ORDER BY id',fetch=True); rows=[]
    for c in cs: rows.append([{'text':str(c['name']),'callback_data':f'cat:{c["id"]}'}])
    rows.append([{'text':'🏠 Home','callback_data':'home'}])
    render_feature(cid,'tasks','💼 Available Tasks','একটি কাজ নির্বাচন করুন।',markup(rows))
def history(cid):
    rows=db.execute('SELECT * FROM submissions WHERE telegram_id=%s ORDER BY id DESC LIMIT 15',(cid,),True)
    out='\n'.join(f"• <b>{esc(r['category_name'])}</b> — ৳{float(r['reward']):.2f} — <b>{esc(r['status'])}</b>" for r in rows) or 'কোনো submission নেই।'
    render_feature(cid,'history','📜 History','আপনার কাজের History নিচে দেখুন।\n\n'+out,markup([[{'text':'🏠 Home','callback_data':'home'}]]))
def leaderboard(cid):
    rows=db.execute("SELECT telegram_id,first_name,balance FROM users WHERE verified=1 ORDER BY balance DESC LIMIT 20",fetch=True)
    kb=[]
    for i,r in enumerate(rows,1): kb.append([{'text':f"{i}. {r['first_name']} — ৳{float(r['balance']):.2f}",'callback_data':f'lb:{r["telegram_id"]}'}])
    kb.append([{'text':'🏠 Home','callback_data':'home'}])
    render_feature(cid,'leaderboard','🏆 Leaderboard','সেরা Earners-দের তালিকা।',markup(kb))
def referral(cid):
    me=api('getMe').get('result',{}); bot=me.get('username','YourBot'); link=f'https://t.me/{bot}?start=ref_{cid}'
    bonus=float(setting('referral_bonus','1'))
    share='https://t.me/share/url?url='+quote(link)+'&text='+quote('Join our bot and start earning!')
    kb=markup([[{'text':'📤 Share Referral Link','url':share}],[{'text':'👥 My Ref','callback_data':'myref'}],[{'text':'🏠 Home','callback_data':'home'}]])
    render_feature(cid,'referral','🔗 Referral',f'বন্ধু Invite করে Bonus পান।\n\n<b>Referral Link</b>\n<code>{esc(link)}</code>\n\nVerified referral bonus: <b>৳{bonus:.2f}</b>',kb)
def myref(cid):
    rows=db.execute('SELECT first_name,telegram_id,verified FROM users WHERE referred_by=%s ORDER BY id DESC',(cid,),True)
    out='\n'.join(f"• {esc(r['first_name'])} — {'✅ Verified' if r['verified'] else '⏳ Unverified'}" for r in rows) or 'কোনো referral নেই।'
    render_feature(cid,'myref','👥 My Ref','আপনার Referral List।\n\n'+out,markup([[{'text':'🏠 Home','callback_data':'home'}]]))
def withdraw(cid):
    u=user(cid); methods=[x.strip() for x in setting('withdraw_methods','bKash,Nagad,Binance').split(',') if x.strip()]
    rows=[[{'text':m,'callback_data':'wdm:'+str(i)}] for i,m in enumerate(methods)]
    rows.append([{'text':'🏠 Home','callback_data':'home'}])
    render_feature(cid,'withdraw','💸 Withdraw',f'আপনার Balance Withdraw করুন।\n\nMinimum: <b>৳{float(setting("withdraw_min","10")):.2f}</b>\nBalance: <b>৳{float(u["balance"]):.2f}</b>\n\nPayment method নির্বাচন করুন।',markup(rows))
def admin_menu(cid):
    send(cid,'<b>🛠 Admin Panel</b>\n\nনিচের অপশন থেকে নির্বাচন করুন।',markup([
        [{'text':'📊 Dashboard','callback_data':'adm:dash'}],[{'text':'➕ Add Task','callback_data':'adm:add'}],[{'text':'📋 Manage Tasks','callback_data':'adm:tasks'}],
        [{'text':'📤 Submissions','callback_data':'adm:subs'}],[{'text':'💸 Withdrawals','callback_data':'adm:wds'}],[{'text':'👥 Users','callback_data':'adm:users'}],
        [{'text':'🏆 Leaderboard','callback_data':'adm:lb'}],[{'text':'🔗 Referral Settings','callback_data':'adm:ref'}],[{'text':'🎨 Design','callback_data':'adm:design'}],[{'text':'⚙️ Settings','callback_data':'adm:set'}]
    ]))

def admin_dash(cid):
    counts={}
    for table in ['users','categories','submissions','withdrawals']:
        counts[table]=db.execute(f'SELECT COUNT(*) n FROM {table}',fetch=True,one=True)['n']
    send(cid,f"<b>📊 Dashboard</b>\n\n👥 Users: <b>{counts['users']}</b>\n📋 Tasks: <b>{counts['categories']}</b>\n📤 Submissions: <b>{counts['submissions']}</b>\n💸 Withdrawals: <b>{counts['withdrawals']}</b>",markup([[{'text':'⬅️ Admin Panel','callback_data':'adm:menu'}]]))

def admin_tasks(cid):
    cs=db.execute('SELECT * FROM categories ORDER BY id',fetch=True); rows=[]
    for c in cs: rows.append([{'text':('🟢 ' if c['active'] else '🔴 ')+str(c['name']),'callback_data':f'admt:{c["id"]}'}])
    rows.append([{'text':'➕ Add Task','callback_data':'adm:add'}]); rows.append([{'text':'⬅️ Admin Panel','callback_data':'adm:menu'}]); send(cid,'<b>📋 Manage Tasks</b>',markup(rows))

def admin_task_view(cid,tid):
    c=db.execute('SELECT * FROM categories WHERE id=%s',(tid,),True,True)
    if not c:return
    send(cid,f"<b>{esc(c['name'])}</b>\n\nReward: ৳{float(c['reward']):.2f}\nStatus: {'ON' if c['active'] else 'OFF'}\nPassword: <code>{esc(c['today_password'])}</code>\n\n{esc(c['details'] or c['description'] or '')}",markup([
        [{'text':'✏️ Edit Task','callback_data':f'admedit:{tid}'}],[{'text':'🔄 Toggle Active','callback_data':f'admtoggle:{tid}'}],[{'text':'🗑 Delete Task','callback_data':f'admdel:{tid}'}],[{'text':'⬅️ Tasks','callback_data':'adm:tasks'}]
    ]))

def start_add(cid):
    setstate(cid,'admin_add','step=1'); send(cid,'<b>➕ Add Task</b>\n\n১/৮ — Task name লিখুন।\n\nCancel লিখলে বন্ধ হবে।')

def admin_add_input(cid,text):
    st,data=state(cid); step=int(re.search(r'step=(\d+)',data).group(1)); vals={}
    for part in data.split(';'):
        if '=' in part:
            k,v=part.split('=',1); vals[k]=v
    if text.lower()=='cancel': setstate(cid,'home',''); admin_menu(cid); return
    prompts={1:'Task name',2:'Reward amount',3:'Today Password',4:'Details',5:'Description',6:'Logo URL/file_id (optional, send - to skip)',7:'Task Image URL/file_id (optional, send - to skip)',8:'Submit prompt 1 (optional, - to default)'}
    if step==2:
        try: Decimal(text)
        except: send(cid,'❌ Reward সঠিক সংখ্যা দিন।'); return
    vals[f'v{step}']=text
    if step>=8:
        name=vals['v1']; reward=vals['v2']; pw=vals['v3']; details=vals['v4']; desc=vals['v5']; logo='' if vals['v6']=='-' else vals['v6']; img='' if vals['v7']=='-' else vals['v7']; p1='' if vals['v8']=='-' else vals['v8']
        db.execute("INSERT INTO categories(name,reward,today_password,details,description,logo,task_image,submit_prompt1,submit_prompt2,submit_button_text,password_label,active) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,1)",(name,reward,pw,details,desc,logo,img,p1,'📎 এখন দ্বিতীয় প্রয়োজনীয় তথ্য/Proof পাঠান।','📤 Submit Job','🔐 আজকের Password'))
        setstate(cid,'home',''); send(cid,'✅ <b>Task Added Successfully!</b>',markup([[{'text':'📋 Manage Tasks','callback_data':'adm:tasks'}],[{'text':'🛠 Admin Panel','callback_data':'adm:menu'}]])); return
    nd=';'.join([f'{k}={v}' for k,v in vals.items() if k.startswith('v')])+f';step={step+1}'
    setstate(cid,'admin_add',nd); send(cid,f'<b>➕ Add Task</b>\n\n{step+1}/8 — {prompts[step+1]} লিখুন।')

def notify_admin_submission(sid):
    s=db.execute('SELECT * FROM submissions WHERE id=%s',(sid,),True,True)
    if not s:return
    send(ADMIN_CHAT_ID,f"<b>📤 New Submission #{sid}</b>\n👤 {esc(s['category_name'])}\n🆔 <code>{s['telegram_id']}</code>\n📝 Account/Info: <code>{esc(s['account_number'])}</code>\n📎 Proof: <code>{esc(s['proof'])}</code>\n💰 Reward: ৳{float(s['reward']):.2f}",markup([[{'text':'✅ Approve','callback_data':f'ap:{sid}'},{'text':'❌ Reject','callback_data':f'ar:{sid}'}]]))

def process_submission(cid,text):
    st,data=state(cid); m=re.match(r'submit(\d)\|(.+)',data or '')
    if not m:return False
    step=int(m.group(1)); tid=int(m.group(2)); c=db.execute('SELECT * FROM categories WHERE id=%s AND active=1',(tid,),True,True)
    if not c: setstate(cid,'home',''); return True
    if step==1:
        setstate(cid,'submit2',str(tid)+'|'+text); send(cid,esc(c['submit_prompt2'] or '📎 এখন দ্বিতীয় প্রয়োজনীয় তথ্য/Proof পাঠান।'),markup([[{'text':'❌ Cancel','callback_data':'cancel_submit'}]])); return True
    # duplicate protection
    du=db.execute("SELECT id FROM submissions WHERE telegram_id=%s AND category_id=%s AND status IN ('pending','approved') LIMIT 1",(cid,tid),True,True)
    if du: setstate(cid,'home',''); send(cid,'⚠️ এই Task ইতিমধ্যে Submit করা হয়েছে।',keyboard(user(cid)['language'])); return True
    first=text
    # data stores first|second for step2
    if data.startswith(str(tid)+'|'): first=data.split('|',1)[1]
    db.execute("INSERT INTO submissions(telegram_id,category_id,category_name,account_number,proof,reward,status) VALUES(%s,%s,%s,%s,%s,%s,'pending')",(cid,tid,c['name'],first,text,c['reward']))
    sid=db.execute('SELECT last_insert_rowid() id',fetch=True,one=True)['id']
    db.execute('UPDATE users SET pending_balance=pending_balance+%s,state=%s WHERE telegram_id=%s',(c['reward'],'home',cid)); setstate(cid,'home',''); notify_admin_submission(sid); send(cid,'⏳ <b>Submission Submitted</b>\n\nAdmin review করবে।',keyboard(user(cid)['language'])); return True

def message(cid,m):
    text=(m.get('text') or '').strip(); first=m.get('from',{}).get('first_name','User'); u=user(cid,first)
    st,data=state(cid)
    if cid==ADMIN_CHAT_ID and m.get('photo'):
        fid=m['photo'][-1].get('file_id'); send(cid,f'🆔 <b>Telegram Photo file_id</b>\n\n<code>{esc(fid)}</code>'); return
    if st=='admin_add': admin_add_input(cid,text); return
    if st.startswith('admin_edit:'): admin_edit_input(cid,text); return
    if st=='design_edit': design_input(cid,text); return
    if st.startswith('submit'):
        if text in ['/start','🏠 Home','💼 কাজ করুন','💼 Work','📜 History','🏆 Leaderboard','🎧 Support','🔗 Referral','👥 My Ref','🌐 Language','🎬 Tutorial','💸 Withdraw']:
            send(cid,'🔒 <b>Submission চলছে</b>\n\nশেষ করুন অথবা Cancel চাপুন।',markup([[{'text':'❌ Cancel Submission','callback_data':'cancel_submit'}]])); return
        if process_submission(cid,text): return
    if st.startswith('wd_amount:'):
        try: amount=Decimal(text)
        except: send(cid,'❌ সঠিক amount দিন।'); return
        method=st.split(':',1)[1]; u=user(cid); mn=Decimal(setting('withdraw_min','10'))
        if amount<mn or amount>Decimal(str(u['balance'])): send(cid,f'❌ Invalid amount. Minimum ৳{mn:.2f}, Balance ৳{Decimal(str(u["balance"])):.2f}'); return
        setstate(cid,'wd_account',f'{method}|{amount}'); send(cid,f'💳 <b>{esc(method)} Account</b>\n\nAccount number/ID পাঠান।',markup([[{'text':'❌ Cancel','callback_data':'cancel_wd'}]])); return
    if st.startswith('wd_account'):
        method,amount=data.split('|',1); amount=Decimal(amount); u=user(cid)
        if amount>Decimal(str(u['balance'])): setstate(cid,'home',''); home(cid); return
        wid=db.execute("INSERT INTO withdrawals(telegram_id,amount,method,account,status) VALUES(%s,%s,%s,%s,'pending')",(cid,amount,method,text))
        db.execute('UPDATE users SET balance=balance-%s,state=%s WHERE telegram_id=%s',(amount,'home',cid)); setstate(cid,'home','')
        send(ADMIN_CHAT_ID,f"💸 <b>New Withdrawal #{wid}</b>\n👤 {esc(u['first_name'])}\n🆔 <code>{cid}</code>\n💳 {esc(method)}\n💰 ৳{amount:.2f}\n📱 <code>{esc(text)}</code>",markup([[{'text':'✅ Approve','callback_data':f'wa:{wid}'},{'text':'❌ Reject','callback_data':f'wr:{wid}'}]]))
        send(cid,'⏳ <b>Withdrawal Submitted</b>',keyboard(u['language'])); return
    if text=='/admin' and cid==ADMIN_CHAT_ID: admin_menu(cid); return
    if text.startswith('/start'):
        payload=text[6:].strip()
        if payload.startswith('ref_') and not u['referred_by']:
            ref=int(payload[4:] or 0)
            if ref and ref!=cid and db.execute('SELECT telegram_id FROM users WHERE telegram_id=%s',(ref,),True,True): db.execute('UPDATE users SET referred_by=%s WHERE telegram_id=%s AND (referred_by IS NULL OR referred_by=0)',(ref,cid))
        if not u['verified']: setstate(cid,'await_handle',''); verify_start(cid)
        else: home(cid)
        return
    if not u['verified']:
        if st=='await_handle':
            given=text.lstrip('@'); expected=setting('verify_handle',VERIFY_HANDLE).lstrip('@')
            if given.lower()==expected.lower():
                db.execute("UPDATE users SET verified=1,state='home' WHERE telegram_id=%s",(cid,)); setstate(cid,'home','')
                fresh=user(cid); ref=int(fresh['referred_by'] or 0); bonus=Decimal(setting('referral_bonus','1'))
                if ref and not fresh['referral_bonus_awarded'] and int(setting('referral_enabled','1')):
                    refu=db.execute('SELECT * FROM users WHERE telegram_id=%s AND verified=1',(ref,),True,True)
                    if refu:
                        db.execute('UPDATE users SET balance=balance+%s WHERE telegram_id=%s',(bonus,ref)); db.execute('UPDATE users SET referral_bonus_awarded=1 WHERE telegram_id=%s',(cid,)); send(ref,f'🎉 <b>Referral Bonus!</b>\n\n💰 Bonus: <b>৳{bonus:.2f}</b>',keyboard(refu['language']))
                send(cid,'✅ <b>Verification Successful!</b>',keyboard(fresh['language']))
            else: send(cid,f'❌ <b>Wrong Handle!</b>\n\n<code>{esc(expected)}</code>')
        else: verify_start(cid)
        return
    if text in ('🏠 Home','/start'): home(cid)
    elif text in ('💼 কাজ করুন','💼 Work'): tasks(cid)
    elif text=='📜 History': history(cid)
    elif text=='🏆 Leaderboard': leaderboard(cid)
    elif text=='🔗 Referral': referral(cid)
    elif text=='👥 My Ref': myref(cid)
    elif text=='💸 Withdraw': withdraw(cid)
    elif text=='🎧 Support': render_feature(cid,'support','🎧 Support',setting('support_text','প্রয়োজনে Support-এ যোগাযোগ করুন।'))
    elif text=='🎬 Tutorial': render_feature(cid,'tutorial','🎬 Tutorial',setting('tutorial_text','Bot ব্যবহার করার Tutorial।'))
    elif text=='🌐 Language': render_feature(cid,'language','🌐 Language','আপনার ভাষা নির্বাচন করুন।',markup([[{'text':'🇧🇩 বাংলা','callback_data':'lang:bn'},{'text':'🇬🇧 English','callback_data':'lang:en'}],[{'text':'🏠 Home','callback_data':'home'}]]))
    else: send(cid,'❓ Menu থেকে একটি অপশন নির্বাচন করুন।',keyboard(u['language']))

def admin_edit_input(cid,text):
    st,data=state(cid); tid=int(st.split(':',1)[1]); step=int(data.split(':',1)[0]); c=db.execute('SELECT * FROM categories WHERE id=%s',(tid,),True,True)
    if text.lower()=='cancel': setstate(cid,'home',''); admin_task_view(cid,tid); return
    fields=['name','reward','today_password','details','description','logo','task_image','submit_prompt1','submit_prompt2','submit_button_text','password_label']
    if step<=len(fields):
        f=fields[step-1]
        val=None if text=='-' and f in ('logo','task_image') else text
        db.execute(f'UPDATE categories SET `{f}`=%s WHERE id=%s',(val,tid))
    if step>=len(fields): setstate(cid,'home',''); admin_task_view(cid,tid); return
    setstate(cid,f'admin_edit:{tid}',str(step+1)); send(cid,f'✏️ Edit {step+1}/{len(fields)} — <b>{fields[step]}</b> লিখুন।')

def callbacks(q):
    cid=int(q['message']['chat']['id']); data=q.get('data',''); answer(q.get('id','')); u=user(cid)
    if data.startswith('adm:') and cid==ADMIN_CHAT_ID:
        a=data[4:]
        if a=='menu': admin_menu(cid)
        elif a=='dash': admin_dash(cid)
        elif a=='add': start_add(cid)
        elif a=='tasks': admin_tasks(cid)
        elif a=='subs': admin_subs(cid)
        elif a=='wds': admin_wds(cid)
        elif a=='users': admin_users(cid)
        elif a=='lb': leaderboard(cid)
        elif a=='ref': admin_ref(cid)
        elif a=='design': admin_design(cid)
        elif a=='set': admin_settings(cid)
        return
    if data.startswith('design:') and cid==ADMIN_CHAT_ID: design_editor(cid,data[7:]); return
    if data.startswith('admt:') and cid==ADMIN_CHAT_ID: admin_task_view(cid,int(data[5:])); return
    if data.startswith('admedit:') and cid==ADMIN_CHAT_ID:
        tid=int(data[7:]); setstate(cid,f'admin_edit:{tid}','1'); send(cid,'✏️ Edit 1/11 — <b>name</b> লিখুন।'); return
    if data.startswith('admtoggle:') and cid==ADMIN_CHAT_ID:
        tid=int(data[10:]); db.execute('UPDATE categories SET active=1-active WHERE id=%s',(tid,)); admin_task_view(cid,tid); return
    if data.startswith('admdel:') and cid==ADMIN_CHAT_ID:
        tid=int(data[7:]); db.execute('DELETE FROM categories WHERE id=%s',(tid,)); send(cid,'🗑 Task deleted.',markup([[{'text':'⬅️ Tasks','callback_data':'adm:tasks'}]])); return
    if data.startswith('ap:') and cid==ADMIN_CHAT_ID: admin_sub_action(cid,int(data[3:]),True); return
    if data.startswith('ar:') and cid==ADMIN_CHAT_ID: admin_sub_action(cid,int(data[3:]),False); return
    if data.startswith('wa:') and cid==ADMIN_CHAT_ID: admin_wd_action(cid,int(data[3:]),True); return
    if data.startswith('wr:') and cid==ADMIN_CHAT_ID: admin_wd_action(cid,int(data[3:]),False); return
    if data=='start_verify': setstate(cid,'await_handle',''); send(cid,'🔐 Handle কপি করে পাঠান।'); return
    if data=='home': home(cid); return
    if data=='tasks': tasks(cid); return
    if data.startswith('cat:'): task(cid,int(data[4:])); return
    if data.startswith('pass:'):
        c=db.execute('SELECT * FROM categories WHERE id=%s AND active=1',(int(data[5:]),),True,True)
        if c: send(cid,f"🔐 <b>{esc(c['password_label'] or 'আজকের Password')}</b>\n\n<code>{esc(c['today_password'])}</code>\n\n{esc(c['alert_text'] or setting('alert_text'))}",markup([[{'text':c['copy_button_text'] or '📋 Copy Password','copy_text':{'text':str(c['today_password'])}}],[{'text':c['submit_button_text'] or '📤 Submit Job','callback_data':f'submit:{c["id"]}'}],[{'text':'⬅️ Back','callback_data':f'cat:{c["id"]}'}]]))
        return
    if data.startswith('details:'):
        c=db.execute('SELECT * FROM categories WHERE id=%s AND active=1',(int(data[8:]),),True,True)
        if c: send(cid,f"<b>{esc(c['name'])}</b>\n\n{esc(c['details'] or c['description'] or '')}\n\n{esc(c['alert_text'] or setting('alert_text'))}",markup([[{'text':c['submit_button_text'] or '📤 Submit Job','callback_data':f'submit:{c["id"]}'}],[{'text':'⬅️ Back','callback_data':f'cat:{c["id"]}'}]]))
        return
    if data.startswith('submit:'):
        tid=int(data[7:]); setstate(cid,'submit1',str(tid)); c=db.execute('SELECT * FROM categories WHERE id=%s',(tid,),True,True); send(cid,f"📤 <b>{esc(c['name'])}</b>\n\n{esc(c['submit_prompt1'] or '📝 প্রথমে প্রয়োজনীয় তথ্য পাঠান।')}",markup([[{'text':'❌ Cancel','callback_data':'cancel_submit'}]])); return
    if data=='cancel_submit': setstate(cid,'home',''); home(cid); return
    if data=='cancel_wd': setstate(cid,'home',''); home(cid); return
    if data.startswith('wdm:'):
        idx=int(data[4:]); methods=[x.strip() for x in setting('withdraw_methods','bKash,Nagad,Binance').split(',') if x.strip()]
        if idx<len(methods): setstate(cid,'wd_amount:'+methods[idx],''); send(cid,f'💸 <b>{esc(methods[idx])}</b>\n\nAmount লিখুন।\nMinimum: ৳{float(setting("withdraw_min","10")):.2f}',markup([[{'text':'❌ Cancel','callback_data':'cancel_wd'}]])); return
    if data.startswith('lang:'):
        l='en' if data[5:]=='en' else 'bn'; db.execute('UPDATE users SET language=%s WHERE telegram_id=%s',(l,cid)); home(cid); return
    if data=='myref': myref(cid); return
    if data=='referral_open': referral(cid); return
    if data=='leaderboard': leaderboard(cid); return
    if data.startswith('lb:'):
        tid=int(data[3:]); r=db.execute('SELECT first_name,balance,pending_balance FROM users WHERE telegram_id=%s AND verified=1',(tid,),True,True)
        if r: send(cid,f"<b>👤 {esc(r['first_name'])}</b>\n\n💰 Balance: ৳{float(r['balance']):.2f}\n⏳ Pending: ৳{float(r['pending_balance']):.2f}",markup([[{'text':'⬅️ Leaderboard','callback_data':'leaderboard'}]]))
        return

def admin_sub_action(cid,sid,approve):
    s=db.execute("SELECT * FROM submissions WHERE id=%s AND status='pending'",(sid,),True,True)
    if not s:return
    db.execute('UPDATE submissions SET status=%s WHERE id=%s',('approved' if approve else 'rejected',sid))
    if approve: db.execute('UPDATE users SET pending_balance=MAX(0,pending_balance-%s),balance=balance+%s WHERE telegram_id=%s',(s['reward'],s['reward'],s['telegram_id']))
    else: db.execute('UPDATE users SET pending_balance=MAX(0,pending_balance-%s) WHERE telegram_id=%s',(s['reward'],s['telegram_id']))
    send(s['telegram_id'],'🎉 <b>কাজ Approved!</b>' if approve else '❌ <b>কাজ Reject হয়েছে।</b>',keyboard(user(s['telegram_id'])['language']))
    send(cid,'✅ Done.',markup([[{'text':'📤 Submissions','callback_data':'adm:subs'}]]))

def admin_wd_action(cid,wid,approve):
    w=db.execute("SELECT * FROM withdrawals WHERE id=%s AND status='pending'",(wid,),True,True)
    if not w:return
    db.execute('UPDATE withdrawals SET status=%s,updated_at=CURRENT_TIMESTAMP WHERE id=%s',('approved' if approve else 'rejected',wid))
    if not approve: db.execute('UPDATE users SET balance=balance+%s WHERE telegram_id=%s',(w['amount'],w['telegram_id']))
    send(w['telegram_id'],'✅ <b>Withdrawal Approved!</b>' if approve else '❌ <b>Withdrawal Rejected</b>\n\nAmount Balance-এ ফেরত দেওয়া হয়েছে.',keyboard(user(w['telegram_id'])['language']))
    send(cid,'✅ Done.',markup([[{'text':'💸 Withdrawals','callback_data':'adm:wds'}]]))

def admin_subs(cid):
    rows=db.execute("SELECT * FROM submissions WHERE status='pending' ORDER BY id DESC LIMIT 20",fetch=True)
    if not rows: send(cid,'📤 কোনো pending submission নেই.',markup([[{'text':'⬅️ Admin Panel','callback_data':'adm:menu'}]])); return
    for s in rows: send(cid,f"<b>#{s['id']} — {esc(s['category_name'])}</b>\n🆔 <code>{s['telegram_id']}</code>\n📝 {esc(s['account_number'])}\n📎 {esc(s['proof'])}\n💰 ৳{float(s['reward']):.2f}",markup([[{'text':'✅ Approve','callback_data':f'ap:{s["id"]}'},{'text':'❌ Reject','callback_data':f'ar:{s["id"]}'}]]))

def admin_wds(cid):
    rows=db.execute("SELECT * FROM withdrawals WHERE status='pending' ORDER BY id DESC LIMIT 20",fetch=True)
    if not rows: send(cid,'💸 কোনো pending withdrawal নেই.',markup([[{'text':'⬅️ Admin Panel','callback_data':'adm:menu'}]])); return
    for w in rows: send(cid,f"<b>#{w['id']}</b>\n🆔 <code>{w['telegram_id']}</code>\n💳 {esc(w['method'])}\n💰 ৳{float(w['amount']):.2f}\n📱 <code>{esc(w['account'])}</code>",markup([[{'text':'✅ Approve','callback_data':f'wa:{w["id"]}'},{'text':'❌ Reject','callback_data':f'wr:{w["id"]}'}]]))

def admin_users(cid):
    n=db.execute('SELECT COUNT(*) n FROM users',fetch=True,one=True)['n']; v=db.execute('SELECT COUNT(*) n FROM users WHERE verified=1',fetch=True,one=True)['n']; send(cid,f'<b>👥 Users</b>\n\nTotal: {n}\nVerified: {v}',markup([[{'text':'⬅️ Admin Panel','callback_data':'adm:menu'}]]))
def admin_ref(cid): send(cid,f"<b>🔗 Referral Settings</b>\n\nEnabled: {setting('referral_enabled','1')}\nBonus: ৳{float(setting('referral_bonus','1')):.2f}\n\nপরিবর্তন করতে নিচের command ব্যবহার করুন:\n<code>/setbonus 2</code>\n<code>/ref on</code> / <code>/ref off</code>",markup([[{'text':'⬅️ Admin Panel','callback_data':'adm:menu'}]]))
def admin_design(cid):
    items=[('home','🏠 Home'),('tasks','💼 Work'),('history','📜 History'),('leaderboard','🏆 Leaderboard'),('referral','🔗 Referral'),('myref','👥 My Ref'),('withdraw','💸 Withdraw'),('support','🎧 Support'),('tutorial','🎬 Tutorial'),('language','🌐 Language'),('welcome','👋 Welcome')]
    rows=[[{'text':label,'callback_data':f'design:{key}'}] for key,label in items]
    rows.append([{'text':'⬅️ Admin Panel','callback_data':'adm:menu'}])
    send(cid,'<b>🎨 Design Manager</b>\n\nযে পেজের Design পরিবর্তন করতে চান সেটি নির্বাচন করুন।',markup(rows))

def design_editor(cid,feature):
    title=setting(f'design_{feature}_title','')
    text=setting(f'design_{feature}_text','')
    image=setting(f'design_{feature}_image','')
    setstate(cid,'design_edit',json.dumps({'feature':feature,'step':1},ensure_ascii=False))
    send(cid,f'<b>🎨 Edit Design: {esc(feature)}</b>\n\nবর্তমান Title: <code>{esc(title)}</code>\nবর্তমান Text: <code>{esc(text)}</code>\nবর্তমান Image: <code>{esc(image) if image else "(none)"}</code>\n\n1/3 — নতুন Title পাঠান।\n<code>-</code> দিলে আগের Title থাকবে।')

def design_input(cid,text):
    st,data=state(cid)
    try: info=json.loads(data)
    except: setstate(cid,'home',''); admin_design(cid); return
    feature=info['feature']; step=int(info['step'])
    if text.lower()=='cancel': setstate(cid,'home',''); admin_design(cid); return
    if step==1:
        if text!='-': set_setting(f'design_{feature}_title',text)
        info['step']=2; setstate(cid,'design_edit',json.dumps(info,ensure_ascii=False)); send(cid,'2/3 — নতুন Description/Text পাঠান।\n<code>-</code> দিলে আগের Text থাকবে।'); return
    if step==2:
        if text!='-': set_setting(f'design_{feature}_text',text)
        info['step']=3; setstate(cid,'design_edit',json.dumps(info,ensure_ascii=False)); send(cid,'3/3 — Image URL বা Telegram <b>file_id</b> পাঠান।\n<code>-</code> দিলে Image থাকবে না।'); return
    if text!='-': set_setting(f'design_{feature}_image',text)
    else: set_setting(f'design_{feature}_image','')
    setstate(cid,'home',''); send(cid,'✅ <b>Design Updated!</b>',markup([[{'text':'🎨 Design','callback_data':'adm:design'}],[{'text':'🛠 Admin Panel','callback_data':'adm:menu'}]]))

def admin_settings(cid): send(cid,f"<b>⚙️ Settings</b>\n\nMinimum Withdraw: ৳{float(setting('withdraw_min','10')):.2f}\nMethods: {esc(setting('withdraw_methods','bKash,Nagad,Binance'))}\nAuto Clean: {setting('auto_delete_enabled','0')}",markup([[{'text':'⬅️ Admin Panel','callback_data':'adm:menu'}]]))

def admin_command(cid,text):
    if cid!=ADMIN_CHAT_ID:return False
    if text.startswith('/setbonus '): set_setting('referral_bonus',text.split(' ',1)[1]); send(cid,'✅ Referral bonus updated.'); return True
    if text=='/ref on': set_setting('referral_enabled','1'); send(cid,'✅ Referral enabled.'); return True
    if text=='/ref off': set_setting('referral_enabled','0'); send(cid,'✅ Referral disabled.'); return True
    if text.startswith('/setmin '): set_setting('withdraw_min',text.split(' ',1)[1]); send(cid,'✅ Minimum withdrawal updated.'); return True
    if text.startswith('/setmethods '): set_setting('withdraw_methods',text.split(' ',1)[1]); send(cid,'✅ Withdrawal methods updated.'); return True
    if text.startswith('/sethomeimage '): set_setting('home_image',text.split(' ',1)[1]); send(cid,'✅ Home image updated.'); return True
    if text.startswith('/setwelcomeimage '): set_setting('welcome_image',text.split(' ',1)[1]); send(cid,'✅ Welcome image updated.'); return True
    return False


# =========================
# UPGRADE: Dynamic task steps + Message Manager + Keyboard Manager
# =========================

def ensure_upgrade_schema():
    c=db.conn()
    try:
        c.execute("""CREATE TABLE IF NOT EXISTS task_steps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER NOT NULL,
            step_no INTEGER NOT NULL,
            prompt TEXT NOT NULL,
            input_type TEXT DEFAULT 'text',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(category_id, step_no)
        )""")
        # Existing installations get this column without losing old data.
        cols=[r[1] for r in c.execute("PRAGMA table_info(submissions)").fetchall()]
        if 'answers_json' not in cols:
            c.execute("ALTER TABLE submissions ADD COLUMN answers_json TEXT DEFAULT ''")
        c.commit()
    finally:
        c.close()

    # Migrate old fixed two-step tasks into task_steps.
    cats=db.execute("SELECT * FROM categories ORDER BY id",fetch=True)
    for cat in cats:
        n=db.execute("SELECT COUNT(*) n FROM task_steps WHERE category_id=%s",(cat['id'],),True,True)['n']
        if int(n)==0:
            p1=cat.get('submit_prompt1') or '📝 প্রথমে প্রয়োজনীয় তথ্য পাঠান।'
            p2=cat.get('submit_prompt2') or '📎 এখন দ্বিতীয় প্রয়োজনীয় তথ্য/Proof পাঠান।'
            db.execute("INSERT OR IGNORE INTO task_steps(category_id,step_no,prompt,input_type) VALUES(%s,1,%s,'text')",(cat['id'],p1))
            db.execute("INSERT OR IGNORE INTO task_steps(category_id,step_no,prompt,input_type) VALUES(%s,2,%s,'text')",(cat['id'],p2))

    kb_defaults={
        'kb_home':'1','kb_work':'1','kb_history':'1','kb_leaderboard':'1',
        'kb_support':'1','kb_referral':'1','kb_myref':'1','kb_withdraw':'1',
        'kb_tutorial':'1','kb_language':'1'
    }
    for k,v in kb_defaults.items():
        set_setting(k,v)

ensure_upgrade_schema()


def kb_on(key):
    return setting('kb_'+key,'1') == '1'


def keyboard(lang='bn'):
    # Each main keyboard button can be turned ON/OFF independently from Admin Panel.
    rows=[]
    home_btn='🏠 Home'
    work_btn='💼 Work' if lang=='en' else '💼 কাজ করুন'
    if kb_on('home') or kb_on('work'):
        row=[]
        if kb_on('home'): row.append(home_btn)
        if kb_on('work'): row.append(work_btn)
        if row: rows.append(row)
    row=[]
    if kb_on('history'): row.append('📜 History')
    if kb_on('leaderboard'): row.append('🏆 Leaderboard')
    if row: rows.append(row)
    row=[]
    if kb_on('support'): row.append('🎧 Support')
    if kb_on('referral'): row.append('🔗 Referral')
    if row: rows.append(row)
    row=[]
    if kb_on('myref'): row.append('👥 My Ref')
    if kb_on('withdraw'): row.append('💸 Withdraw')
    if row: rows.append(row)
    if kb_on('tutorial'): rows.append(['🎬 Tutorial'])
    if kb_on('language'): rows.append(['🌐 Language'])
    return markup(rows,True)


def task_steps(tid):
    return db.execute("SELECT * FROM task_steps WHERE category_id=%s ORDER BY step_no",(tid,),True)


def task_step_count(tid):
    return db.execute("SELECT COUNT(*) n FROM task_steps WHERE category_id=%s",(tid,),True,True)['n']


def task(cid,tid):
    c=db.execute('SELECT * FROM categories WHERE id=%s AND active=1',(tid,),True,True)
    if not c:return
    L=user(cid)['language']
    kb=markup([
        [{'text':c['password_label'] or ('🔐 Today Password' if L=='en' else '🔐 আজকের Password'),'callback_data':f'pass:{tid}'}],
        [{'text':'📖 Details','callback_data':f'details:{tid}'}],
        [{'text':c['submit_button_text'] or ('📤 Submit Job' if L=='en' else '📤 Submit Job'),'callback_data':f'submit:{tid}'}],
        [{'text':'⬅️ Back','callback_data':'tasks'}]
    ])
    p=c.get('task_image_file_id') or c.get('task_image')
    l=c.get('logo_file_id') or c.get('logo')
    if p and photo(cid,p,esc(c['name']),kb).get('ok'):
        if l and l!=p: photo(cid,l,'')
        return
    if l and photo(cid,l,esc(c['name']),kb).get('ok'): return
    send(cid,esc(c['name']),kb)


def admin_menu(cid):
    send(cid,'<b>🛠 Admin Panel</b>\n\nনিচের অপশন থেকে আলাদা আলাদা Section নির্বাচন করুন।',markup([
        [{'text':'📊 Dashboard','callback_data':'adm:dash'}],
        [{'text':'➕ Add Task','callback_data':'adm:add'}],
        [{'text':'📋 Manage Tasks','callback_data':'adm:tasks'}],
        [{'text':'📤 Submissions','callback_data':'adm:subs'}],
        [{'text':'💸 Withdrawals','callback_data':'adm:wds'}],
        [{'text':'👥 Users','callback_data':'adm:users'}],
        [{'text':'🏆 Leaderboard','callback_data':'adm:lb'}],
        [{'text':'🔗 Referral Settings','callback_data':'adm:ref'}],
        [{'text':'💬 Messages','callback_data':'adm:msg'}],
        [{'text':'⌨️ Keyboard','callback_data':'adm:kb'}],
        [{'text':'🎨 Design','callback_data':'adm:design'}],
        [{'text':'⚙️ Settings','callback_data':'adm:set'}]
    ]))


# ---------- Dynamic Add Task ----------

ADD_FIELDS = [
    ('name','Task name'),
    ('reward','Reward amount'),
    ('today_password','Today Password'),
    ('details','Details'),
    ('description','Description'),
    ('logo','Logo URL/file_id (optional, - to skip)'),
    ('task_image','Task Image URL/file_id (optional, - to skip)'),
    ('alert_text','Task Alert Text (optional, - to use global alert)'),
    ('password_label','Password Button Label (optional, - for default)'),
    ('copy_button_text','Copy Button Text (optional, - for default)'),
    ('submit_button_text','Submit Button Text (optional, - for default)'),
    ('step_count','How many information pages/steps? Example: 2 or 5')
]


def start_add(cid):
    data={'step':1,'vals':{}}
    setstate(cid,'admin_add',json.dumps(data,ensure_ascii=False))
    send(cid,'<b>➕ Add Task</b>\n\n1/12 — <b>Task name</b> লিখুন।\n\nCancel লিখলে বন্ধ হবে।')


def admin_add_input(cid,text):
    st,data=state(cid)
    try: info=json.loads(data)
    except: info={'step':1,'vals':{}}
    if text.lower()=='cancel':
        setstate(cid,'home',''); admin_menu(cid); return

    step=int(info.get('step',1))
    vals=info.get('vals',{})
    field,label=ADD_FIELDS[step-1]

    if field=='reward':
        try: Decimal(text)
        except:
            send(cid,'❌ Reward সঠিক সংখ্যা দিন।'); return
    if field=='step_count':
        try:
            n=int(text)
            if n<1 or n>20: raise ValueError
        except:
            send(cid,'❌ Step সংখ্যা 1 থেকে 20-এর মধ্যে দিন।'); return
    vals[field]=text
    info['vals']=vals

    if field=='step_count':
        info['step']=13
        info['step_prompts']={}
        setstate(cid,'admin_add',json.dumps(info,ensure_ascii=False))
        send(cid,f'13/{12+int(vals["step_count"])} — <b>Step 1-এর জন্য কী তথ্য চাইবেন?</b>\n\nউদাহরণ: Telegram Username / Account Number / Screenshot Link')
        return

    if step<12:
        info['step']=step+1
        setstate(cid,'admin_add',json.dumps(info,ensure_ascii=False))
        send(cid,f'<b>➕ Add Task</b>\n\n{step+1}/12 — <b>{ADD_FIELDS[step][1]}</b> লিখুন।')
        return

    # This branch is only reachable if step_count is somehow skipped; normally step 12 routes above.
    finalize_add_task(cid,info)


def finalize_add_task(cid,info):
    vals=info.get('vals',{})
    name=vals.get('name','Untitled Task')
    reward=vals.get('reward','0')
    pw=vals.get('today_password','')
    details=vals.get('details','')
    desc=vals.get('description','')
    logo='' if vals.get('logo','')=='-' else vals.get('logo','')
    img='' if vals.get('task_image','')=='-' else vals.get('task_image','')
    alert='' if vals.get('alert_text','')=='-' else vals.get('alert_text','')
    plabel='' if vals.get('password_label','')=='-' else vals.get('password_label','')
    ctext='' if vals.get('copy_button_text','')=='-' else vals.get('copy_button_text','')
    stext='' if vals.get('submit_button_text','')=='-' else vals.get('submit_button_text','')
    n=int(vals.get('step_count',1))
    tid=db.execute("""INSERT INTO categories
        (name,reward,today_password,details,description,logo,task_image,alert_text,
         submit_prompt1,submit_prompt2,submit_button_text,copy_button_text,password_label,active)
        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,1)""",
        (name,reward,pw,details,desc,logo,img,alert,'','','📤 Submit Job','📋 Copy Password','🔐 আজকের Password'))
    # Keep old fields compatible.
    prompts=info.get('step_prompts',{})
    for i in range(1,n+1):
        prompt=prompts.get(str(i)) or f'📝 Step {i}: প্রয়োজনীয় তথ্য পাঠান।'
        db.execute("INSERT INTO task_steps(category_id,step_no,prompt,input_type) VALUES(%s,%s,%s,'text')",(tid,i,prompt))
    if n>=1: db.execute("UPDATE categories SET submit_prompt1=%s WHERE id=%s",(prompts.get('1',''),tid))
    if n>=2: db.execute("UPDATE categories SET submit_prompt2=%s WHERE id=%s",(prompts.get('2',''),tid))
    setstate(cid,'home','')
    send(cid,f'✅ <b>Task Added Successfully!</b>\n\n📌 {esc(name)}\n📄 Information Steps: <b>{n}</b>',markup([
        [{'text':'📋 Manage Tasks','callback_data':'adm:tasks'}],
        [{'text':'🛠 Admin Panel','callback_data':'adm:menu'}]
    ]))


# Replace the final part of add flow with dynamic prompts.
_old_admin_add_input = admin_add_input
def admin_add_input(cid,text):
    st,data=state(cid)
    try: info=json.loads(data)
    except:
        info={'step':1,'vals':{}}
    if text.lower()=='cancel':
        setstate(cid,'home',''); admin_menu(cid); return
    step=int(info.get('step',1))
    vals=info.get('vals',{})
    prompts=info.get('step_prompts',{})

    if step<=12:
        field,label=ADD_FIELDS[step-1]
        if field=='reward':
            try: Decimal(text)
            except: send(cid,'❌ Reward সঠিক সংখ্যা দিন।'); return
        if field=='step_count':
            try:
                n=int(text)
                if n<1 or n>20: raise ValueError
            except:
                send(cid,'❌ Step সংখ্যা 1 থেকে 20-এর মধ্যে দিন (maximum 20)।'); return
            vals[field]=str(n); info['vals']=vals; info['step']=13
            info['step_prompts']={}
            setstate(cid,'admin_add',json.dumps(info,ensure_ascii=False))
            send(cid,f'13/{12+n} — <b>Step 1-এর Prompt</b>\n\nএই Step-এ User কী তথ্য পাঠাবে সেটা লিখুন।')
            return
        vals[field]=text
        info['vals']=vals
        info['step']=step+1
        setstate(cid,'admin_add',json.dumps(info,ensure_ascii=False))
        send(cid,f'<b>➕ Add Task</b>\n\n{step+1}/12 — <b>{ADD_FIELDS[step][1]}</b> লিখুন।')
        return

    n=int(vals.get('step_count','1'))
    step_no=step-12
    prompts[str(step_no)]=text
    info['step_prompts']=prompts
    if step_no<n:
        info['step']=step+1
        setstate(cid,'admin_add',json.dumps(info,ensure_ascii=False))
        send(cid,f'{step+1}/{12+n} — <b>Step {step_no+1}-এর Prompt</b>\n\nএই Step-এ User কী তথ্য পাঠাবে সেটা লিখুন।')
        return
    finalize_add_task(cid,info)


# ---------- Task Editor ----------

def admin_task_view(cid,tid):
    c=db.execute('SELECT * FROM categories WHERE id=%s',(tid,),True,True)
    if not c:return
    n=task_step_count(tid)
    send(cid,f"<b>{esc(c['name'])}</b>\n\n"
             f"💰 Reward: ৳{float(c['reward']):.2f}\n"
             f"📄 Information Steps: <b>{n}</b>\n"
             f"🔘 Status: {'ON' if c['active'] else 'OFF'}\n"
             f"🔐 Password: <code>{esc(c['today_password'])}</code>\n\n"
             f"{esc(c['details'] or c['description'] or '')}",markup([
        [{'text':'✏️ Basic Info','callback_data':f'tedit:{tid}:basic'}],
        [{'text':'🖼 Media','callback_data':f'tedit:{tid}:media'}],
        [{'text':'📝 Submission Steps','callback_data':f'tedit:{tid}:steps'}],
        [{'text':'💬 Task Messages','callback_data':f'tedit:{tid}:msg'}],
        [{'text':'🔄 Toggle Active','callback_data':f'admtoggle:{tid}'}],
        [{'text':'🗑 Delete Task','callback_data':f'admdel:{tid}'}],
        [{'text':'⬅️ Tasks','callback_data':'adm:tasks'}]
    ]))


def task_edit_section(cid,tid,section):
    c=db.execute('SELECT * FROM categories WHERE id=%s',(tid,),True,True)
    if not c:return
    if section=='basic':
        fields=[('name','Task Name'),('reward','Reward'),('today_password','Today Password'),('details','Details'),('description','Description')]
    elif section=='media':
        fields=[('logo','Logo URL/file_id'),('task_image','Task Image URL/file_id')]
    elif section=='msg':
        fields=[('alert_text','Alert Text'),('password_label','Password Button Label'),('copy_button_text','Copy Button Text'),('submit_button_text','Submit Button Text')]
    else:
        steps=task_steps(tid)
        rows=[[{'text':f"✏️ Step {s['step_no']}",'callback_data':f'tstep:{tid}:{s["step_no"]}'}] for s in steps]
        rows.append([{'text':'➕ Add Step','callback_data':f'tstepadd:{tid}'}])
        rows.append([{'text':'🔢 Change Step Count','callback_data':f'tstepcount:{tid}'}])
        rows.append([{'text':'⬅️ Task','callback_data':f'admt:{tid}'}])
        send(cid,f'<b>📝 Submission Steps</b>\n\nCurrent steps: <b>{len(steps)}</b>\nপ্রতিটি Step আলাদাভাবে Edit করতে পারবেন।',markup(rows)); return

    rows=[]
    for key,label in fields:
        rows.append([{'text':f'✏️ {label}','callback_data':f'tfield:{tid}:{key}'}])
    rows.append([{'text':'⬅️ Task','callback_data':f'admt:{tid}'}])
    send(cid,f'<b>✏️ Edit {esc(section.title())}</b>',markup(rows))


def start_task_field_edit(cid,tid,key):
    setstate(cid,'task_field_edit',json.dumps({'tid':tid,'key':key},ensure_ascii=False))
    c=db.execute('SELECT * FROM categories WHERE id=%s',(tid,),True,True)
    send(cid,f'✏️ <b>{esc(key)}</b>\n\nবর্তমান value:\n<code>{esc(c[key] or "")}</code>\n\nনতুন value পাঠান।\n<code>-</code> দিলে খালি হবে।\nCancel লিখলে বাতিল।')


def task_field_input(cid,text):
    st,data=state(cid)
    try: info=json.loads(data)
    except: setstate(cid,'home',''); return
    tid=int(info['tid']); key=info['key']
    if text.lower()=='cancel':
        setstate(cid,'home',''); admin_task_view(cid,tid); return
    c=db.execute('SELECT * FROM categories WHERE id=%s',(tid,),True,True)
    if not c:return
    if key=='reward':
        try: Decimal(text)
        except: send(cid,'❌ Reward সঠিক সংখ্যা দিন।'); return
    val='' if text=='-' else text
    db.execute(f'UPDATE categories SET `{key}`=%s WHERE id=%s',(val,tid))
    setstate(cid,'home','')
    send(cid,'✅ Updated.',markup([[{'text':'⬅️ Task','callback_data':f'admt:{tid}'}]]))


def edit_step_prompt(cid,tid,step_no):
    s=db.execute("SELECT * FROM task_steps WHERE category_id=%s AND step_no=%s",(tid,step_no),True,True)
    if not s:return
    setstate(cid,'task_step_edit',json.dumps({'tid':tid,'step':step_no},ensure_ascii=False))
    send(cid,f'✏️ <b>Step {step_no} Prompt</b>\n\nCurrent:\n<code>{esc(s["prompt"])}</code>\n\nনতুন Prompt পাঠান।')


def task_step_input(cid,text):
    st,data=state(cid)
    try: info=json.loads(data)
    except: setstate(cid,'home',''); return
    tid=int(info['tid']); no=int(info['step'])
    if text.lower()=='cancel':
        setstate(cid,'home',''); task_edit_section(cid,tid,'steps'); return
    db.execute("UPDATE task_steps SET prompt=%s WHERE category_id=%s AND step_no=%s",(text,tid,no))
    if no==1: db.execute("UPDATE categories SET submit_prompt1=%s WHERE id=%s",(text,tid))
    if no==2: db.execute("UPDATE categories SET submit_prompt2=%s WHERE id=%s",(text,tid))
    setstate(cid,'home','')
    send(cid,'✅ Step Prompt Updated.',markup([[{'text':'📝 Submission Steps','callback_data':f'tedit:{tid}:steps'}],[{'text':'⬅️ Task','callback_data':f'admt:{tid}'}]]))


def add_task_step(cid,tid):
    n=task_step_count(tid)+1
    if n>20:
        send(cid,'❌ Maximum 20 steps allowed.'); return
    setstate(cid,'task_step_add',json.dumps({'tid':tid,'step':n},ensure_ascii=False))
    send(cid,f'➕ <b>Step {n} Prompt</b>\n\nএই Step-এ User কী তথ্য পাঠাবে তা লিখুন।')


def task_step_add_input(cid,text):
    st,data=state(cid)
    try: info=json.loads(data)
    except: setstate(cid,'home',''); return
    tid=int(info['tid']); no=int(info['step'])
    if text.lower()=='cancel':
        setstate(cid,'home',''); task_edit_section(cid,tid,'steps'); return
    db.execute("INSERT OR IGNORE INTO task_steps(category_id,step_no,prompt,input_type) VALUES(%s,%s,%s,'text')",(tid,no,text))
    if no==1: db.execute("UPDATE categories SET submit_prompt1=%s WHERE id=%s",(text,tid))
    if no==2: db.execute("UPDATE categories SET submit_prompt2=%s WHERE id=%s",(text,tid))
    setstate(cid,'home','')
    task_edit_section(cid,tid,'steps')


def change_task_step_count(cid,tid):
    setstate(cid,'task_step_count',json.dumps({'tid':tid},ensure_ascii=False))
    send(cid,f'🔢 বর্তমান Step: <b>{task_step_count(tid)}</b>\n\nনতুন Step সংখ্যা দিন (1-20)।')


def task_step_count_input(cid,text):
    st,data=state(cid)
    try: info=json.loads(data); tid=int(info['tid']); n=int(text)
    except: send(cid,'❌ 1-20 এর একটি সংখ্যা দিন।'); return
    if n<1 or n>20: send(cid,'❌ 1-20 এর মধ্যে দিন।'); return
    current=task_step_count(tid)
    if n>current:
        for no in range(current+1,n+1):
            db.execute("INSERT OR IGNORE INTO task_steps(category_id,step_no,prompt,input_type) VALUES(%s,%s,%s,'text')",(tid,no,f'📝 Step {no}: প্রয়োজনীয় তথ্য পাঠান।'))
    elif n<current:
        db.execute("DELETE FROM task_steps WHERE category_id=%s AND step_no>%s",(tid,n))
    # Keep legacy first two fields synchronized.
    steps=task_steps(tid)
    p1=next((x['prompt'] for x in steps if x['step_no']==1),'')
    p2=next((x['prompt'] for x in steps if x['step_no']==2),'')
    db.execute("UPDATE categories SET submit_prompt1=%s,submit_prompt2=%s WHERE id=%s",(p1,p2,tid))
    setstate(cid,'home','')
    task_edit_section(cid,tid,'steps')


# ---------- Dynamic Submission ----------

def submission_value(m):
    if m.get('text') is not None:
        return m.get('text','').strip()
    if m.get('photo'):
        return '[PHOTO_FILE_ID]'+m['photo'][-1].get('file_id','')
    if m.get('document'):
        return '[DOCUMENT_FILE_ID]'+m['document'].get('file_id','')
    if m.get('video'):
        return '[VIDEO_FILE_ID]'+m['video'].get('file_id','')
    return ''


def notify_admin_submission(sid):
    s=db.execute('SELECT * FROM submissions WHERE id=%s',(sid,),True,True)
    if not s:return
    try: answers=json.loads(s.get('answers_json') or '{}')
    except: answers={}
    lines=[]
    for k,v in answers.items():
        lines.append(f"<b>Step {esc(k)}</b>\n<code>{esc(v)}</code>")
    body='\n\n'.join(lines) or f"<code>{esc(s['account_number'])}</code>\n<code>{esc(s['proof'])}</code>"
    send(ADMIN_CHAT_ID,
         f"<b>📤 New Submission #{sid}</b>\n"
         f"👤 {esc(s['category_name'])}\n"
         f"🆔 <code>{s['telegram_id']}</code>\n"
         f"💰 Reward: ৳{float(s['reward']):.2f}\n\n"
         f"{body}",
         markup([[{'text':'✅ Approve','callback_data':f'ap:{sid}'},{'text':'❌ Reject','callback_data':f'ar:{sid}'}]]))


def process_submission(cid,m):
    st,data=state(cid)
    if st!='submit': return False
    try: info=json.loads(data)
    except:
        setstate(cid,'home',''); return True
    tid=int(info['tid']); step=int(info.get('step',1)); answers=info.get('answers',{})
    c=db.execute('SELECT * FROM categories WHERE id=%s AND active=1',(tid,),True,True)
    if not c:
        setstate(cid,'home',''); return True

    value=submission_value(m)
    if not value:
        send(cid,'❌ কোনো তথ্য পাওয়া যায়নি। Text/Photo/Document পাঠান।'); return True

    steps=task_steps(tid)
    if step<1 or step>len(steps):
        setstate(cid,'home',''); return True

    answers[str(step)]=value

    # Duplicate protection before final insert.
    if step==1:
        du=db.execute("SELECT id FROM submissions WHERE telegram_id=%s AND category_id=%s AND status IN ('pending','approved') LIMIT 1",(cid,tid),True,True)
        if du:
            setstate(cid,'home',''); send(cid,'⚠️ এই Task ইতিমধ্যে Submit করা হয়েছে।',keyboard(user(cid)['language'])); return True

    if step < len(steps):
        info={'tid':tid,'step':step+1,'answers':answers}
        setstate(cid,'submit',json.dumps(info,ensure_ascii=False))
        nxt=steps[step]
        send(cid,esc(nxt['prompt']),markup([[{'text':'❌ Cancel Submission','callback_data':'cancel_submit'}]]))
        return True

    first=answers.get('1','')
    second=answers.get('2','')
    answers_json=json.dumps(answers,ensure_ascii=False)
    sid=db.execute("""INSERT INTO submissions
        (telegram_id,category_id,category_name,account_number,proof,reward,status,answers_json)
        VALUES(%s,%s,%s,%s,%s,%s,'pending',%s)""",
        (cid,tid,c['name'],first,second,c['reward'],answers_json))
    db.execute('UPDATE users SET pending_balance=pending_balance+%s,state=%s WHERE telegram_id=%s',(c['reward'],'home',cid))
    setstate(cid,'home','')
    notify_admin_submission(sid)
    send(cid,'⏳ <b>Submission Submitted</b>\n\nসব তথ্য Admin-এর কাছে পাঠানো হয়েছে। Admin review করবে।',keyboard(user(cid)['language']))
    return True


# ---------- Message Manager ----------

MESSAGE_FIELDS=[
    ('welcome_text','Welcome Message'),
    ('alert_text','Global Task Alert'),
    ('pending_alert','Pending Alert'),
    ('support_text','Support Text'),
    ('tutorial_text','Tutorial Text'),
    ('verify_handle','Verify Handle'),
    ('verify_link','Verify Link')
]


def admin_messages(cid):
    rows=[[{'text':f'✏️ {label}','callback_data':f'msgedit:{key}'}] for key,label in MESSAGE_FIELDS]
    rows += [
        [{'text':'✏️ Approved Message','callback_data':'msgedit:approved_msg'}],
        [{'text':'✏️ Rejected Message','callback_data':'msgedit:rejected_msg'}],
        [{'text':'⬅️ Admin Panel','callback_data':'adm:menu'}]
    ]
    send(cid,'<b>💬 Message Manager</b>\n\nপ্রতিটি message আলাদা Section থেকে Edit করুন।',markup(rows))


def start_message_edit(cid,key):
    setstate(cid,'message_edit',json.dumps({'key':key},ensure_ascii=False))
    current=setting(key,'')
    send(cid,f'<b>💬 Edit: {esc(key)}</b>\n\nবর্তমান:\n<code>{esc(current)}</code>\n\nনতুন Text পাঠান। HTML tags ব্যবহার করা যাবে।')


def message_edit_input(cid,text):
    st,data=state(cid)
    try: info=json.loads(data)
    except: setstate(cid,'home',''); return
    key=info['key']
    if text.lower()=='cancel':
        setstate(cid,'home',''); admin_messages(cid); return
    set_setting(key,text)
    setstate(cid,'home','')
    send(cid,'✅ Message Updated.',markup([[{'text':'💬 Messages','callback_data':'adm:msg'}],[{'text':'🛠 Admin Panel','callback_data':'adm:menu'}]]))


# ---------- Keyboard Manager ----------

KB_FIELDS=[
    ('home','🏠 Home'),('work','💼 Work'),('history','📜 History'),
    ('leaderboard','🏆 Leaderboard'),('support','🎧 Support'),('referral','🔗 Referral'),
    ('myref','👥 My Ref'),('withdraw','💸 Withdraw'),('tutorial','🎬 Tutorial'),
    ('language','🌐 Language')
]


def admin_keyboard(cid):
    rows=[]
    for key,label in KB_FIELDS:
        status='🟢 ON' if kb_on(key) else '🔴 OFF'
        rows.append([{'text':f'{status} {label}','callback_data':f'kbt:{key}'}])
    rows.append([{'text':'⬅️ Admin Panel','callback_data':'adm:menu'}])
    send(cid,'<b>⌨️ Keyboard Manager</b>\n\nযে Button hide/show করতে চান সেটিতে চাপুন।',markup(rows))


def toggle_keyboard(key,cid):
    set_setting('kb_'+key,'0' if kb_on(key) else '1')
    admin_keyboard(cid)


# ---------- Settings ----------

def admin_settings(cid):
    send(cid,
         f"<b>⚙️ General Settings</b>\n\n"
         f"Minimum Withdraw: ৳{float(setting('withdraw_min','10')):.2f}\n"
         f"Methods: {esc(setting('withdraw_methods','bKash,Nagad,Binance'))}\n"
         f"Referral: {'ON' if setting('referral_enabled','1')=='1' else 'OFF'}\n"
         f"Auto Clean: {setting('auto_delete_enabled','0')}\n\n"
         f"Commands:\n"
         f"<code>/setmin 10</code>\n<code>/setmethods bKash,Nagad,Binance</code>\n"
         f"<code>/setbonus 2</code>\n<code>/ref on</code> / <code>/ref off</code>",
         markup([[{'text':'💬 Messages','callback_data':'adm:msg'}],
                 [{'text':'⌨️ Keyboard','callback_data':'adm:kb'}],
                 [{'text':'⬅️ Admin Panel','callback_data':'adm:menu'}]]))


# ---------- Submission list with all dynamic answers ----------

def admin_subs(cid):
    rows=db.execute("SELECT * FROM submissions WHERE status='pending' ORDER BY id DESC LIMIT 20",fetch=True)
    if not rows:
        send(cid,'📤 কোনো pending submission নেই.',markup([[{'text':'⬅️ Admin Panel','callback_data':'adm:menu'}]])); return
    for s in rows:
        try: answers=json.loads(s.get('answers_json') or '{}')
        except: answers={}
        details=[]
        for k,v in answers.items():
            details.append(f"Step {esc(k)}: <code>{esc(v)}</code>")
        body='\n'.join(details) or f"{esc(s['account_number'])}\n{esc(s['proof'])}"
        send(cid,f"<b>#{s['id']} — {esc(s['category_name'])}</b>\n"
                 f"🆔 <code>{s['telegram_id']}</code>\n💰 ৳{float(s['reward']):.2f}\n\n{body}",
             markup([[{'text':'✅ Approve','callback_data':f'ap:{s["id"]}'},{'text':'❌ Reject','callback_data':f'ar:{s["id"]}'}]]))


# ---------- New callbacks ----------

def callbacks(q):
    cid=int(q['message']['chat']['id']); data=q.get('data',''); answer(q.get('id','')); u=user(cid)

    if data.startswith('adm:') and cid==ADMIN_CHAT_ID:
        a=data[4:]
        if a=='menu': admin_menu(cid)
        elif a=='dash': admin_dash(cid)
        elif a=='add': start_add(cid)
        elif a=='tasks': admin_tasks(cid)
        elif a=='subs': admin_subs(cid)
        elif a=='wds': admin_wds(cid)
        elif a=='users': admin_users(cid)
        elif a=='lb': leaderboard(cid)
        elif a=='ref': admin_ref(cid)
        elif a=='design': admin_design(cid)
        elif a=='set': admin_settings(cid)
        elif a=='msg': admin_messages(cid)
        elif a=='kb': admin_keyboard(cid)
        return

    if cid==ADMIN_CHAT_ID and data.startswith('msgedit:'):
        start_message_edit(cid,data[8:]); return
    if cid==ADMIN_CHAT_ID and data.startswith('kbt:'):
        toggle_keyboard(data[4:],cid); return

    if cid==ADMIN_CHAT_ID and data.startswith('tedit:'):
        _,tid,section=data.split(':',2); task_edit_section(cid,int(tid),section); return
    if cid==ADMIN_CHAT_ID and data.startswith('tfield:'):
        _,tid,key=data.split(':',2); start_task_field_edit(cid,int(tid),key); return
    if cid==ADMIN_CHAT_ID and data.startswith('tstep:'):
        _,tid,no=data.split(':',2); edit_step_prompt(cid,int(tid),int(no)); return
    if cid==ADMIN_CHAT_ID and data.startswith('tstepadd:'):
        add_task_step(cid,int(data.split(':')[1])); return
    if cid==ADMIN_CHAT_ID and data.startswith('tstepcount:'):
        change_task_step_count(cid,int(data.split(':')[1])); return

    if cid==ADMIN_CHAT_ID and data.startswith('admt:'):
        admin_task_view(cid,int(data[5:])); return
    if cid==ADMIN_CHAT_ID and data.startswith('admedit:'):
        admin_task_view(cid,int(data[8:])); return
    if cid==ADMIN_CHAT_ID and data.startswith('admtoggle:'):
        tid=int(data[10:]); db.execute('UPDATE categories SET active=1-active WHERE id=%s',(tid,)); admin_task_view(cid,tid); return
    if cid==ADMIN_CHAT_ID and data.startswith('admdel:'):
        tid=int(data[7:])
        db.execute('DELETE FROM task_steps WHERE category_id=%s',(tid,))
        db.execute('DELETE FROM categories WHERE id=%s',(tid,))
        send(cid,'🗑 Task deleted.',markup([[{'text':'⬅️ Tasks','callback_data':'adm:tasks'}]])); return
    if data.startswith('design:') and cid==ADMIN_CHAT_ID:
        design_editor(cid,data[7:]); return
    if data.startswith('ap:') and cid==ADMIN_CHAT_ID:
        admin_sub_action(cid,int(data[3:]),True); return
    if data.startswith('ar:') and cid==ADMIN_CHAT_ID:
        admin_sub_action(cid,int(data[3:]),False); return
    if data.startswith('wa:') and cid==ADMIN_CHAT_ID:
        admin_wd_action(cid,int(data[3:]),True); return
    if data.startswith('wr:') and cid==ADMIN_CHAT_ID:
        admin_wd_action(cid,int(data[3:]),False); return

    if data=='start_verify':
        setstate(cid,'await_handle',''); send(cid,'🔐 Handle কপি করে পাঠান।'); return
    if data=='home': home(cid); return
    if data=='tasks': tasks(cid); return
    if data.startswith('cat:'): task(cid,int(data[4:])); return

    if data.startswith('pass:'):
        c=db.execute('SELECT * FROM categories WHERE id=%s AND active=1',(int(data[5:]),),True,True)
        if c:
            send(cid,f"🔐 <b>{esc(c['password_label'] or 'আজকের Password')}</b>\n\n"
                     f"<code>{esc(c['today_password'])}</code>\n\n"
                     f"{esc(c['alert_text'] or setting('alert_text'))}",
                 markup([
                     [{'text':c['copy_button_text'] or '📋 Copy Password',
                       'copy_text':{'text':str(c['today_password'])}}],
                     [{'text':c['submit_button_text'] or '📤 Submit Job','callback_data':f'submit:{c["id"]}'}],
                     [{'text':'⬅️ Back','callback_data':f'cat:{c["id"]}'}]
                 ]))
        return

    if data.startswith('details:'):
        c=db.execute('SELECT * FROM categories WHERE id=%s AND active=1',(int(data[8:]),),True,True)
        if c:
            send(cid,f"<b>{esc(c['name'])}</b>\n\n{esc(c['details'] or c['description'] or '')}\n\n"
                     f"{esc(c['alert_text'] or setting('alert_text'))}",
                 markup([[{'text':c['submit_button_text'] or '📤 Submit Job','callback_data':f'submit:{c["id"]}'}],
                         [{'text':'⬅️ Back','callback_data':f'cat:{c["id"]}'}]]))
        return

    if data.startswith('submit:'):
        tid=int(data[7:])
        c=db.execute('SELECT * FROM categories WHERE id=%s AND active=1',(tid,),True,True)
        if not c:return
        du=db.execute("SELECT id FROM submissions WHERE telegram_id=%s AND category_id=%s AND status IN ('pending','approved') LIMIT 1",(cid,tid),True,True)
        if du:
            send(cid,'⚠️ এই Task ইতিমধ্যে Submit করা হয়েছে।',keyboard(u['language'])); return
        steps=task_steps(tid)
        if not steps:
            send(cid,'❌ এই Task-এর submission steps সেট করা হয়নি। Admin-কে জানান.'); return
        info={'tid':tid,'step':1,'answers':{}}
        setstate(cid,'submit',json.dumps(info,ensure_ascii=False))
        send(cid,f"📤 <b>{esc(c['name'])}</b>\n\n{esc(steps[0]['prompt'])}",
             markup([[{'text':'❌ Cancel Submission','callback_data':'cancel_submit'}]])); return

    if data=='cancel_submit':
        setstate(cid,'home',''); home(cid); return
    if data=='cancel_wd':
        setstate(cid,'home',''); home(cid); return
    if data.startswith('wdm:'):
        idx=int(data[4:]); methods=[x.strip() for x in setting('withdraw_methods','bKash,Nagad,Binance').split(',') if x.strip()]
        if idx<len(methods):
            setstate(cid,'wd_amount:'+methods[idx],'')
            send(cid,f'💸 <b>{esc(methods[idx])}</b>\n\nAmount লিখুন.\nMinimum: ৳{float(setting("withdraw_min","10")):.2f}',
                 markup([[{'text':'❌ Cancel','callback_data':'cancel_wd'}]]))
        return
    if data.startswith('lang:'):
        l='en' if data[5:]=='en' else 'bn'
        db.execute('UPDATE users SET language=%s WHERE telegram_id=%s',(l,cid)); home(cid); return
    if data=='myref': myref(cid); return
    if data=='referral_open': referral(cid); return
    if data=='leaderboard': leaderboard(cid); return
    if data.startswith('lb:'):
        tid=int(data[3:]); r=db.execute('SELECT first_name,balance,pending_balance FROM users WHERE telegram_id=%s AND verified=1',(tid,),True,True)
        if r: send(cid,f"<b>👤 {esc(r['first_name'])}</b>\n\n💰 Balance: ৳{float(r['balance']):.2f}\n⏳ Pending: ৳{float(r['pending_balance']):.2f}",markup([[{'text':'⬅️ Leaderboard','callback_data':'leaderboard'}]]))
        return


# ---------- New message dispatcher ----------

def message(cid,m):
    text=(m.get('text') or '').strip()
    first=m.get('from',{}).get('first_name','User')
    u=user(cid,first)
    st,data=state(cid)

    if cid==ADMIN_CHAT_ID and m.get('photo') and not st.startswith(('submit','wd_','await_handle')):
        fid=m['photo'][-1].get('file_id')
        send(cid,f'🆔 <b>Telegram Photo file_id</b>\n\n<code>{esc(fid)}</code>')
        return

    if st=='admin_add': admin_add_input(cid,text); return
    if st=='task_field_edit': task_field_input(cid,text); return
    if st=='task_step_edit': task_step_input(cid,text); return
    if st=='task_step_add': task_step_add_input(cid,text); return
    if st=='task_step_count': task_step_count_input(cid,text); return
    if st=='message_edit': message_edit_input(cid,text); return
    if st=='design_edit': design_input(cid,text); return

    if st=='submit':
        if text in ['/start','🏠 Home','💼 কাজ করুন','💼 Work','📜 History','🏆 Leaderboard','🎧 Support','🔗 Referral','👥 My Ref','🌐 Language','🎬 Tutorial','💸 Withdraw']:
            send(cid,'🔒 <b>Submission চলছে</b>\n\nসব Step শেষ করুন অথবা Cancel চাপুন।',
                 markup([[{'text':'❌ Cancel Submission','callback_data':'cancel_submit'}]])); return
        if process_submission(cid,m): return

    if st.startswith('wd_amount:'):
        try: amount=Decimal(text)
        except: send(cid,'❌ সঠিক amount দিন।'); return
        method=st.split(':',1)[1]; u=user(cid); mn=Decimal(setting('withdraw_min','10'))
        if amount<mn or amount>Decimal(str(u['balance'])):
            send(cid,f'❌ Invalid amount. Minimum ৳{mn:.2f}, Balance ৳{Decimal(str(u["balance"])):.2f}'); return
        setstate(cid,'wd_account',f'{method}|{amount}')
        send(cid,f'💳 <b>{esc(method)} Account</b>\n\nAccount number/ID পাঠান.',
             markup([[{'text':'❌ Cancel','callback_data':'cancel_wd'}]])); return

    if st.startswith('wd_account'):
        method,amount=data.split('|',1); amount=Decimal(amount); u=user(cid)
        if amount>Decimal(str(u['balance'])): setstate(cid,'home',''); home(cid); return
        wid=db.execute("INSERT INTO withdrawals(telegram_id,amount,method,account,status) VALUES(%s,%s,%s,%s,'pending')",(cid,amount,method,text))
        db.execute('UPDATE users SET balance=balance-%s,state=%s WHERE telegram_id=%s',(amount,'home',cid)); setstate(cid,'home','')
        send(ADMIN_CHAT_ID,f"💸 <b>New Withdrawal #{wid}</b>\n👤 {esc(u['first_name'])}\n🆔 <code>{cid}</code>\n💳 {esc(method)}\n💰 ৳{amount:.2f}\n📱 <code>{esc(text)}</code>",
             markup([[{'text':'✅ Approve','callback_data':f'wa:{wid}'},{'text':'❌ Reject','callback_data':f'wr:{wid}'}]]))
        send(cid,'⏳ <b>Withdrawal Submitted</b>',keyboard(u['language'])); return

    if text=='/admin' and cid==ADMIN_CHAT_ID:
        admin_menu(cid); return

    if text.startswith('/start'):
        payload=text[6:].strip()
        if payload.startswith('ref_') and not u['referred_by']:
            try: ref=int(payload[4:] or 0)
            except: ref=0
            if ref and ref!=cid and db.execute('SELECT telegram_id FROM users WHERE telegram_id=%s',(ref,),True,True):
                db.execute('UPDATE users SET referred_by=%s WHERE telegram_id=%s AND (referred_by IS NULL OR referred_by=0)',(ref,cid))
        if not u['verified']:
            setstate(cid,'await_handle',''); verify_start(cid)
        else: home(cid)
        return

    if not u['verified']:
        if st=='await_handle':
            given=text.lstrip('@'); expected=setting('verify_handle',VERIFY_HANDLE).lstrip('@')
            if given.lower()==expected.lower():
                db.execute("UPDATE users SET verified=1,state='home' WHERE telegram_id=%s",(cid,)); setstate(cid,'home','')
                fresh=user(cid); ref=int(fresh['referred_by'] or 0); bonus=Decimal(setting('referral_bonus','1'))
                if ref and not fresh['referral_bonus_awarded'] and int(setting('referral_enabled','1')):
                    refu=db.execute('SELECT * FROM users WHERE telegram_id=%s AND verified=1',(ref,),True,True)
                    if refu:
                        db.execute('UPDATE users SET balance=balance+%s WHERE telegram_id=%s',(bonus,ref))
                        db.execute('UPDATE users SET referral_bonus_awarded=1 WHERE telegram_id=%s',(cid,))
                        send(ref,f'🎉 <b>Referral Bonus!</b>\n\n💰 Bonus: <b>৳{bonus:.2f}</b>',keyboard(refu['language']))
                send(cid,'✅ <b>Verification Successful!</b>',keyboard(fresh['language']))
            else:
                send(cid,f'❌ <b>Wrong Handle!</b>\n\n<code>{esc(expected)}</code>')
        else: verify_start(cid)
        return

    if text in ('🏠 Home','/start'): home(cid)
    elif text in ('💼 কাজ করুন','💼 Work'): tasks(cid)
    elif text=='📜 History': history(cid)
    elif text=='🏆 Leaderboard': leaderboard(cid)
    elif text=='🔗 Referral': referral(cid)
    elif text=='👥 My Ref': myref(cid)
    elif text=='💸 Withdraw': withdraw(cid)
    elif text=='🎧 Support': render_feature(cid,'support','🎧 Support',setting('support_text','প্রয়োজনে Support-এ যোগাযোগ করুন।'))
    elif text=='🎬 Tutorial': render_feature(cid,'tutorial','🎬 Tutorial',setting('tutorial_text','Bot ব্যবহার করার Tutorial।'))
    elif text=='🌐 Language': render_feature(cid,'language','🌐 Language','আপনার ভাষা নির্বাচন করুন।',markup([[{'text':'🇧🇩 বাংলা','callback_data':'lang:bn'},{'text':'🇬🇧 English','callback_data':'lang:en'}],[{'text':'🏠 Home','callback_data':'home'}]]))
    else: send(cid,'❓ Menu থেকে একটি অপশন নির্বাচন করুন।',keyboard(u['language']))


def run():
    offset=0; logging.info('Bot started')
    while True:
        try:
            r=api('getUpdates',offset=offset,timeout=POLL_TIMEOUT,allowed_updates='["message","callback_query"]')
            for upd in r.get('result',[]):
                offset=upd['update_id']+1
                if 'callback_query' in upd: callbacks(upd['callback_query'])
                elif 'message' in upd:
                    m=upd['message']; cid=int(m['chat']['id']); text=(m.get('text') or '').strip()
                    if cid==ADMIN_CHAT_ID and admin_command(cid,text): continue
                    message(cid,m)
        except Exception as e:
            logging.exception('poll error: %s',e); time.sleep(3)

if __name__=='__main__': run()
