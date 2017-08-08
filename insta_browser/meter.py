# -*- coding: utf-8 -*-
import json

try:
    import urllib.request as simple_browser
except ImportError:
    import urllib3 as simple_browser
from .configure import ua

try:
    from urllib import quote
except ImportError:
    from urllib.parse import quote


class InstaMeter:
    user = {}
    posts = []
    __profile_fp_url = 'https://www.instagram.com/{}/?__a=1'
    __profile_rp_url = 'https://www.instagram.com/graphql/query/?query_id=17888483320059182&variables={}'
    __tmp_req_info = None
    __tmp_data = []
    top_posts_liked = []
    top_posts_commented = []
    top_posts_viewed = []
    __error = None

    def __init__(self, username, browser=None, callback=None):
        self.browser = browser
        self.username = username
        self.callback = callback

    def analyze_profile(self):
        try:
            self.__get_profile_first_posts()
        except ValueError as exc:
            self.__error = exc.message
            return self.__error
        self.__get_profile_rest_posts()
        self.__analyze_top_liked_posts()
        self.__analyze_top_commented_posts()
        self.__analyze_top_viewed_posts()

        return json.dumps({
            'account': self.user,
            'posts': self.posts,
            'top_posts_liked': self.top_posts_liked[0:10],
            'top_posts_commented': self.top_posts_commented[0:10],
        }, ensure_ascii=False)

    def __get_profile_first_posts(self):
        url = self.__profile_fp_url.format(self.username)
        try:
            data = json.loads(self.__process_url(url))
        except simple_browser.HTTPError:
            raise ValueError('User not found.')

        self.user['un'] = self.username
        self.user['id'] = data['user']['id']
        self.user['fn'] = data['user']['full_name']
        self.user['f'] = data['user']['follows']['count']
        self.user['fb'] = data['user']['followed_by']['count']
        self.user['p'] = data['user']['media']['count']
        self.user['iv'] = data['user']['is_verified']
        self.user['ip'] = data['user']['is_private']
        self.user['a'] = {'cc': 0, 'lc': 0, 'vv': 0}

        if not self.user['ip']:
            self.__process_posts_first(data['user']['media']['nodes'])
            self.__tmp_req_info = data['user']['media']['page_info']

        if callable(self.callback):
            self.callback(self.user)

    def __get_profile_rest_posts(self):
        if not self.user['ip']:
            while self.__request_for_rest_loop()['has_next_page']:
                pass
            self.__process_posts_rest()

    def __request_for_rest_loop(self):
        var_json = {
            'id': self.user['id'],
            'first': 500 if self.user['p'] > 500 else self.user['p'] - 12,
        }
        if self.__tmp_req_info['has_next_page']:
            var_json.update({'after': self.__tmp_req_info['end_cursor']})
        variable = json.dumps(var_json).replace(' ', '')
        url = self.__profile_rp_url.format(quote(variable))
        data = json.loads(self.__process_url(url))
        self.__tmp_data.extend(data['data']['user']['edge_owner_to_timeline_media']['edges'])
        self.__tmp_req_info = data['data']['user']['edge_owner_to_timeline_media']['page_info']

        return self.__tmp_req_info

    def __process_posts_first(self, posts):
        for post in posts:
            comments = post['comments']['count']
            likes = post['likes']['count']
            self.user['a']['cc'] += comments
            self.user['a']['lc'] += likes
            tmp_post = {
                'id': post['id'],
                'd': post['date'],
                'code': post['code'],
                't': post['caption'],
                'cc': comments,
                'lk': likes,
                'vv': 0,
            }
            if post['is_video']:
                video_views = post['video_views']
                self.user['a']['vv'] += video_views
                tmp_post['vv'] = video_views
            self.posts.append(tmp_post)

    def __process_posts_rest(self):
        for post in self.__tmp_data:
            post = post.values()[0]
            comments = post['edge_media_to_comment']['count']
            likes = post['edge_media_preview_like']['count']
            self.user['a']['cc'] += comments
            self.user['a']['lc'] += likes
            text = post['edge_media_to_caption']['edges']
            tmp_post = {
                'id': post['id'],
                'd': post['taken_at_timestamp'],
                'code': post['shortcode'],
                't': text[0]['node']['text'][0:100] if text else '',
                'cc': comments,
                'lk': likes,
                'vv': 0,
            }
            if post['is_video']:
                video_views = post['video_view_count']
                self.user['a']['vv'] += video_views
                tmp_post['vv'] = video_views
            self.posts.append(tmp_post)

    @staticmethod
    def __process_url(url):
        headers = {
            'User-Agent': ua,
            'Accept': '*/*',
            'Accept-Language': 'en-US',
            'Connection': 'close',
        }
        request = simple_browser.Request(url, headers=headers)
        response = simple_browser.urlopen(request)
        return response.read()

    def __analyze_top_liked_posts(self):
        tmp_posts = list(self.posts)
        tmp_posts.sort(key=lambda post: post['lk'], reverse=True)
        self.top_posts_liked = [post for post in tmp_posts if post['lk'] > 0]

    def __analyze_top_commented_posts(self):
        tmp_posts = list(self.posts)
        tmp_posts.sort(key=lambda post: post['cc'], reverse=True)
        self.top_posts_commented = [post for post in tmp_posts if post['cc'] > 0]

    def __analyze_top_viewed_posts(self):
        tmp_posts = list(self.posts)
        tmp_posts.sort(key=lambda post: post['vv'], reverse=True)
        self.top_posts_viewed = [post for post in tmp_posts if post['vv'] > 0]

    def __check_user_before_print(self):
        if not self.user:
            print('User was not analyzed because of: "{}"'.format(self.__error))
            exit()

    def print_account_statistic(self):
        self.__check_user_before_print()
        stats = {
            'following': self.user['f'],
            'followed': self.user['fb'],
            'posts': self.user['p'],
            'likes': self.user['a']['lc'],
            'comments': self.user['a']['cc'],
            'video views': self.user['a']['vv'],
        }
        print('+-- https://instagram.com/{:-<37}+'.format(self.user['un'] + '/ '))
        print('|   {:<27}|{:^31}|'.format('counter', 'value'))
        print('+{:-^30}+{:-^31}+'.format('', ''))
        for key, value in stats.items():
            print('|   {:<27}|{:^31}|'.format(key, value))
        print('|{: ^62}|'.format(''))
        print('+{:-^62}+'.format(' https://github.com/aLkRicha/insta_browser '))

    def print_top_liked(self, count=10):
        self.__check_user_before_print()
        if not self.user['ip']:
            print('+{:-^62}+'.format('', ''))
            print('|{:^62}|'.format('top liked posts'))
            print('+{:-^62}+'.format('', ''))
            for post in self.top_posts_liked[0:count]:
                text = 'https://instagram.com/p/{}/ - {} likes'.format(post['code'], post['lk'])
                print('|{:^62}|'.format(text))
            print('+{:-^62}+'.format('', ''))

    def print_top_commented(self, count=10):
        self.__check_user_before_print()
        if not self.user['ip']:
            print('+{:-^62}+'.format('', ''))
            print('|{:^62}|'.format('top commented posts'))
            print('+{:-^62}+'.format('', ''))
            for post in self.top_posts_commented[0:count]:
                text = 'https://instagram.com/p/{}/ - {} comments'.format(post['code'], post['cc'])
                print('|{:^62}|'.format(text))
            print('+{:-^62}+'.format(''))

    def print_top_viewed(self, count=10):
        self.__check_user_before_print()
        if not self.user['ip'] and self.top_posts_viewed:
            print('+{:-^62}+'.format('', ''))
            print('|{:^62}|'.format('top viewed posts'))
            print('+{:-^62}+'.format('', ''))
            for post in self.top_posts_viewed[0:count]:
                text = 'https://instagram.com/p/{}/ - {} views'.format(post['code'], post['vv'])
                print('|{:^62}|'.format(text))
            print('+{:-^62}+'.format(''))