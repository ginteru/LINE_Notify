#!/usr/bin/python3

# =========================================#
#   import
# =========================================#
from logging import getLogger
import logging.config
import configparser
import requests
import imaplib
import email
from email.header import decode_header, make_header
import codecs
import chardet
import time
import os
import sys

# =========================================#
#   logging
# =========================================#
# - logging.conf読み込み
#       Windowsではデフォルトエンコーディングがcsp932になることと
#       linuxとwindowsのpythonバージョンが違うことに起因して、osの場合分けで手抜き
if os.name == 'nt':
    logging.config.fileConfig('logging.conf', encoding="utf-8")
else:
    logging.config.fileConfig('logging.conf')

# - loggerの作成
logger = getLogger('main')

# - start log
logger.info('Start Program')


# =========================================#
#   config
# =========================================#
# 設定ファイルを読み込む準備
config_ini = configparser.ConfigParser()
config_ini.read('config.ini', encoding='utf-8')

# セクションを指定して読み込む
config = config_ini['DEFAULT']

# getメソッドで変数を読み込む
SERVER_ADDRESS = config.get('SERVER_ADDRESS')
IMAP_PORT = config.get('IMAP_PORT')
MAIL_ADDRESS = config.get('MAIL_ADDRESS')
MAIL_PASSWORD = config.get('MAIL_PASSWORD')

LINE_TOKEN = config.get('LINE_TOKEN')
LINE_NOTIFY_URL = "https://notify-api.line.me/api/notify"
LINE_HEADERS = {'Authorization': f'Bearer {LINE_TOKEN}'}

# 繰り返し(1分ごと)
INTERVAL_SEC = 10
REPEAT_SET = 5

# 定期的な処理を避けるために待機
#   繰り返しを行っても、終了時刻は大体毎分50秒以降にはならない模様
WAIT_SEC = 50

# 引数で1をもらったときは繰り返し処理なし
args = sys.argv
logger.info('引数の数：{0}'.format(str(len(args))))
if (len(args) == 2) and (args[1] == '1'):
    logger.info('1度だけ実行処理')
    REPEAT_SET = 1
    logger.info('定期処理を避けるために待機:{0}sec'.format(str(WAIT_SEC)))
    time.sleep(WAIT_SEC)


# =========================================#
#   関数
# =========================================#
# msg から文字コードを取得
def get_jp_encoding_name(msg, char_code='iso-2022-jp'):
    try:
        enc = chardet.detect(msg)
        return enc['encoding']
    except:
        return char_code


# msg から本文を取得
def get_content(msg):
    try:
        if msg.is_multipart():
            for pl in msg.get_payload():
                if pl.get_content_type() == "multipart/alternative":
                    for pla in pl.get_payload():
                        if pla.get_content_type() == "text/plain":
                            break
                else:
                    pla = pl
                if pla.get_content_type() == "text/plain":
                    pl2 = pla.get_payload(decode=True)
                    charset = pla.get_content_charset()
                    if not charset:
                        charset = get_jp_encoding_name(pl2)
                    else:
                        charset = get_jp_encoding_name(pl2, charset)
                    try:
                        pl2 = pl2.decode(charset, 'ignore')
                    except:
                        pl2 = pl2.decode()
                    return pl2
        else:
            if msg.get_content_type() == "text/plain":
                pl2 = msg.get_payload(decode=True)
                charset = msg.get_content_charset()
                if not charset:
                    charset = get_jp_encoding_name(pl2)
                else:
                    charset = get_jp_encoding_name(pl2, charset)
                try:
                    pl2 = pl2.decode(charset, 'ignore')
                except:
                    pl2 = pl2.decode()
                return pl2
    except:
        import traceback
        traceback.print_exc()
        return ""


# =========================================#
#   main
# =========================================#
imap = imaplib.IMAP4_SSL(SERVER_ADDRESS, IMAP_PORT)

temp = imap.login(MAIL_ADDRESS, MAIL_PASSWORD)
logger.info('imap.login:{0}'.format(temp))

for counter in range(REPEAT_SET):
    logger.info('繰り返し:{0}回目'.format(str(counter + 1)))

    temp = imap.select("INBOX")
    logger.info('imap.select:{0}'.format(temp))
    
    typ, data = imap.search(None, 'ALL')

    for i in data[0].split():
        logger.info('mail_No.:{0}'.format(i) + '=' * 25)
        ok, x = imap.fetch(i, 'RFC822')
        try:    # 手抜き
            ms = email.message_from_string(x[0][1].decode('iso-2022-jp'))
        except:
            ms = email.message_from_string(x[0][1].decode('UTF-8'))
        
        # 取得したデータを変数に入れる。
        to_ = str(make_header(decode_header(ms["To"])))
        date_ = str(make_header(decode_header(ms["Date"])))
        from_ = str(make_header(decode_header(ms["From"])))
        subject_ = str(make_header(decode_header(ms["Subject"])))
        
        # マルチパート処理
        payload = codecs.decode(get_content(ms), 'unicode-escape')

        # 出力
        # print("to_--------")
        # print(to_)
        logger.info('[TO]:{0}'.format(to_))
        # print("date_--------")
        # print(date_)
        logger.info('[DATE]:{0}'.format(date_))
        # print("from_--------")
        # print(from_)
        logger.info('[FROM]:{0}'.format(from_))
        # print("subject_--------")
        # print(subject_)
        logger.info('[SUBJECT]:{0}'.format(subject_))
        # print("payload--------")
        # print(codecs.decode(payload, 'unicode-escape'))
        logger.info('[PAYLOAD]]:\n{0}\n'.format(payload))

        # LINE Notify
        data = {'message': f'{payload}'}
        requests.post(LINE_NOTIFY_URL, headers=LINE_HEADERS, data=data)

        # メールを格納して削除
        logger.info('メールを格納して削除')
        temp = imap.copy(i, "INBOX.done")
        logger.info('imap.copy:{0}'.format(temp))
        temp = imap.store(i, '+FLAGS', r'(\deleted)')
        logger.info('imap.store-FLAGS:{0}'.format(temp))
    
    # 削除フラグの実行
    temp = imap.expunge()
    logger.info('imap.expunge:{0}'.format(temp))

    # 繰り返し待機
    logger.info('繰り返し:{0}回目終了'.format(str(counter + 1)))
    if not counter == (REPEAT_SET - 1):
        logger.info('繰り返し待機:{0}sec'.format(str(INTERVAL_SEC)))
        time.sleep(INTERVAL_SEC)

logger.info('繰り返し完了')

temp = imap.close()
logger.info('imap.close:{0}'.format(temp))
temp = imap.logout()
logger.info('imap.logout:{0}'.format(temp))

logger.info('End Program')
