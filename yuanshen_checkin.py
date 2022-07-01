import hashlib
import json
import random
import string
import time
import uuid
import os

import requests
from requests.exceptions import HTTPError

class CONFIG:
    ACT_ID = 'e202009291139501'
    APP_VERSION = '2.3.0'
    REFERER_URL = 'https://webstatic.mihoyo.com/bbs/event/signin-ys/index.html?' \
                  'bbs_auth_required={}&act_id={}&utm_source={}&utm_medium={}&' \
                  'utm_campaign={}'.format('true', ACT_ID, 'bbs', 'mys', 'icon')
    AWARD_URL = 'https://api-takumi.mihoyo.com/event/bbs_sign_reward/home?act_id={}'.format(ACT_ID)
    ROLE_URL = 'https://api-takumi.mihoyo.com/binding/api/getUserGameRolesByCookie?game_biz={}'.format('hk4e_cn')
    INFO_URL = 'https://api-takumi.mihoyo.com/event/bbs_sign_reward/info?region={}&act_id={}&uid={}'
    SIGN_URL = 'https://api-takumi.mihoyo.com/event/bbs_sign_reward/sign'
    USER_AGENT = 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) ' \
                 'miHoYoBBS/{}'.format(APP_VERSION)
    MESSGAE_TEMPLATE = '''
    {today:#^28}
    🔅[{region_name}]{uid}
    今日奖励: {award_name} × {award_cnt}
    本月累签: {total_sign_day} 天
    签到结果: {status}
    {end:#^28}'''






def hexdigest(text):
    md5 = hashlib.md5()
    md5.update(text.encode())
    return md5.hexdigest()


class Base(object):
    def __init__(self, cookies: str = None):
        if not isinstance(cookies, str):
            raise TypeError('%s want a %s but got %s' %
                            (self.__class__, type(__name__), type(cookies)))
        self._cookie = cookies

    def get_header(self):
        header = {
            'User-Agent': CONFIG.USER_AGENT,
            'Referer': CONFIG.REFERER_URL,
            'Accept-Encoding': 'gzip, deflate, br',
            'Cookie': self._cookie
        }
        return header

    @staticmethod
    def to_python(json_str: str):
        return json.loads(json_str)

    @staticmethod
    def to_json(obj):
        return json.dumps(obj, indent=4, ensure_ascii=False)


class Roles(Base):
    def get_awards(self):
        response = dict()
        try:
            content = requests.Session().get(
                CONFIG.AWARD_URL, headers=self.get_header()).text
            response = self.to_python(content)
        except json.JSONDecodeError as e:
            print(e)

        return response

    def get_roles(self, max_attempt_number: int = 4):
        print('准备获取账号信息...')
        error = None
        response = dict()

        for i in range(1, max_attempt_number):
            try:
                content = requests.Session().get(
                    CONFIG.ROLE_URL, headers=self.get_header()).text
                response = self.to_python(content)
            except HTTPError as error:
                print(
                    'HTTP error when get game roles, retry %s time(s)...' % i)
                print('error is %s' % error)
                continue
            except KeyError as error:
                print(
                    'Wrong response to get game roles, retry %s time(s)...'% i)
                print('response is %s' % error)
                continue
            except Exception as error:
                print('Unknown error %s, die' % error)
                raise Exception(error)
            error = None
            break

        if error:
            print(
                'Maximum retry times have been reached, error is %s ' % error)
            raise Exception(error)
        if response.get(
            'retcode', 1) != 0 or response.get('data', None) is None:
            raise Exception(response['message'])

        print('账号信息获取完毕')
        return response


class Sign(Base):
    def __init__(self, cookies: str = None):
        super(Sign, self).__init__(cookies)
        self._region_list = []
        self._region_name_list = []
        self._uid_list = []

    @staticmethod
    def get_ds():
        # v2.3.0-web @povsister & @journey-ad
        n = 'h8w582wxwgqvahcdkpvdhbh2w9casgfl'
        i = str(int(time.time()))
        r = ''.join(random.sample(string.ascii_lowercase + string.digits, 6))
        c = hexdigest('salt=' + n + '&t=' + i + '&r=' + r)
        return '{},{},{}'.format(i, r, c)

    def get_header(self):
        header = super(Sign, self).get_header()
        header.update({
            'x-rpc-device_id':str(uuid.uuid3(
                uuid.NAMESPACE_URL, self._cookie)).replace('-', '').upper(),
            # 1:  ios
            # 2:  android
            # 4:  pc web
            # 5:  mobile web
            'x-rpc-client_type': '5',
            'x-rpc-app_version': CONFIG.APP_VERSION,
            'DS': self.get_ds(),
        })
        return header

    def get_info(self):
        user_game_roles = Roles(self._cookie).get_roles()
        role_list = user_game_roles.get('data', {}).get('list', [])

        # role list empty
        if not role_list:
            raise Exception(user_game_roles.get('message', 'Role list empty'))

        print(f'当前账号绑定了 {len(role_list)} 个角色')
        info_list = []
        # cn_gf01:  天空岛
        # cn_qd01:  世界树
        self._region_list = [(i.get('region', 'NA')) for i in role_list]
        self._region_name_list = [(i.get('region_name', 'NA'))
            for i in role_list]
        self._uid_list = [(i.get('game_uid', 'NA')) for i in role_list]

        print('准备获取签到信息...')
        for i in range(len(self._uid_list)):
            info_url = CONFIG.INFO_URL.format(
                self._region_list[i], CONFIG.ACT_ID, self._uid_list[i])
            try:
                content = requests.Session().get(
                    info_url, headers=self.get_header()).text
                info_list.append(self.to_python(content))
            except Exception as e:
                raise Exception(e)

        if not info_list:
            raise Exception('User sign info list is empty')
        print('签到信息获取完毕')
        return info_list

    def run(self):
        info_list = self.get_info()
        message_list = []
        for i in range(len(info_list)):
            today = info_list[i]['data']['today']
            total_sign_day = info_list[i]['data']['total_sign_day']
            awards = Roles(self._cookie).get_awards()['data']['awards']
            uid = str(self._uid_list[i]).replace(
                str(self._uid_list[i])[1:8], '******', 1)

            print(f'准备为旅行者 {i + 1} 号签到...')
            time.sleep(10)
            messgae = {
                'today': today,
                'region_name': self._region_name_list[i],
                'uid': uid,
                'award_name': awards[total_sign_day]['name'],
                'award_cnt': awards[total_sign_day]['cnt'],
                'total_sign_day': total_sign_day,
                'end': '',
            }
            if info_list[i]['data']['is_sign'] is True:
                messgae['award_name'] = awards[total_sign_day - 1]['name']
                messgae['award_cnt'] = awards[total_sign_day - 1]['cnt']
                messgae['status'] = f'👀 旅行者 {i + 1} 号, 你已经签到过了哦'
                message_list.append(self.message.format(**messgae))
                continue
            if info_list[i]['data']['first_bind'] is True:
                messgae['status'] = f'💪 旅行者 {i + 1} 号, 请先前往米游社App手动签到一次'
                message_list.append(self.message.format(**messgae))
                continue

            data = {
                'act_id': CONFIG.ACT_ID,
                'region': self._region_list[i],
                'uid': self._uid_list[i]
            }

            try:
                content = requests.Session().post(
                    CONFIG.SIGN_URL,
                    headers=self.get_header(),
                    data=json.dumps(data, ensure_ascii=False)).text
                response = self.to_python(content)
            except Exception as e:
                raise Exception(e)
            code = response.get('retcode', 99999)
            # 0:      success
            # -5003:  already signed in
            if code != 0:
                message_list.append(response)
                continue
            messgae['total_sign_day'] = total_sign_day + 1
            messgae['status'] = response['message']
            message_list.append(self.message.format(**messgae))
        print('签到完毕')

        return ''.join(message_list)

    @property
    def message(self):
        return CONFIG.MESSGAE_TEMPLATE


def notify_send(WECHAT,msg):
    url1 = 'https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid={}&corpsecret={}'
    req=requests.get(url1.format(WECHAT['corpid'],WECHAT['secret']))
    access_token = json.loads(req.text)['access_token']
    print(msg)
    data = { 
        "touser" : WECHAT['user'],
        "msgtype": "text",
        "agentid" : WECHAT['agentid'],                       
        "text" : {
            "content" : msg
        },
        "safe":0
    }
    data=json.dumps(data)
    data=bytes(data,encoding="utf8")
    url2="https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={}"
    req = requests.post(url=url2.format(access_token), data=data)
    print(req.text)

    

if __name__=="__main__":
    import sys
    import json
    import base64
    b64string=sys.argv[1]
    jstring=base64.b64decode(b64string)
    config=json.loads(jstring)
    print('任务开始')
    msg_list = []
    ret = success_num = fail_num = 0
    COOKIE=config['cookie']
    WECHAT=config['wechat_api']
   
    cookie_list = COOKIE.split('#')
    print(f'检测到共配置了 {len(cookie_list)} 个帐号')
    for i in range(len(cookie_list)):
        print(f'准备为 NO.{i + 1} 账号签到...')
        try:
            msg = f'	NO.{i + 1} 账号:{Sign(cookie_list[i]).run()}'
            msg_list.append(msg)
            success_num = success_num + 1
        except Exception as e:
            msg = f'	NO.{i + 1} 账号:\n    {e}'
            msg_list.append(msg)
            fail_num = fail_num + 1
            print(msg)
            ret = -1
        continue
    print(msg_list)
    notify_send(WECHAT,msg_list[0])
    if ret != 0:
        print('异常退出')
        exit(ret)
    print('任务结束')