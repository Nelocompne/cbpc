import json
import os
import time
from concurrent import futures
from viewing import view
import requests
import math
import argparse

parser = argparse.ArgumentParser(description='help')
parser.add_argument('-u', dest='uid', type=int, help='账号的UID')
args = parser.parse_args()

# 处理原始数据,去掉一些无用信息，让数据更整齐
def ProcessRawData(RawData):
    NewData = {}
    for i in RawData.values():
        media = {
            "id": i['id'],
            "BV": i['bv_id'],
            "是否失效": False,
            "up主": {
                "ID": i['upper']['mid'],
                "昵称": i['upper']['name'],
                "头像": i['upper']['face']
            },
            "视频信息": {
                "标题": i['title'],
                "封面": i['cover'],
                "简介": i['intro'],
                "时长": time.strftime("%H:%M:%S", time.gmtime(i['duration']))
            },
            "观众数据": {
                "播放量": i['cnt_info']['play'],
                "收藏量": i['cnt_info']['collect'],
                "弹幕数量": i['cnt_info']['danmaku']
            },
            "三个时间": {
                "上传时间": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(i['ctime'])),
                "发布时间": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(i['pubtime'])),
                "收藏时间": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(i['fav_time']))
            }
        }
        NewData[media['id']] = media
    return NewData


# 与上一次爬取对比，对于被删除的和自己取消收藏的视频,予以不同的标记
def CompareLastTime(ReadPath, NewData):
    if not os.path.exists(ReadPath):
        return NewData
    with open(ReadPath, 'r', encoding='utf-8') as f:
        OldData = json.load(f)
    # 视频被删除，则保留上次的数据，并且标记
    for i in list(NewData.values()):
        if i['视频信息']['标题'] == "已失效视频" and str(i['id']) in OldData.keys():
            print(OldData[str(i['id'])]['视频信息']['标题'] + '失效了')
            OldData[str(i['id'])]['是否失效'] = True
            NewData[str(i['id'])] = OldData[str(i['id'])]

    # 自己取消收藏，标记
    for i in list(OldData.values()):
        if i['id'] not in NewData.keys():
            print(i['视频信息']['标题'] + '取消了收藏')
            OldData[str(i['id'])]['是否取消了收藏'] = True
            NewData[str(i['id'])] = OldData[str(i['id'])]

    return NewData


# 爬取收藏夹的ID
def GetFavoriteID(WritePath, UID):
    # 请求头
    headers = {'SESSDATA' : 'xxx'}
    url = 'https://api.bilibili.com/x/v3/fav/folder/created/list-all'
    params = {
        'up_mid': args.uid,  # 自己账号的UID
        'jsonp': 'jsonp',
    }
    response = requests.get(url=url, params=params, headers=headers)
    assign = response.json()

    with open(WritePath + '收藏夹id.json', 'w', encoding='utf-8') as fp:
        json.dump(assign, fp, ensure_ascii=False)
    print('收藏夹id爬取成功')


# 爬取一个收藏夹信息，Media_Id代表收藏夹，MaxPage代表收藏夹的页数
def GetOneFavorite(Media_Id, MaxPage):
    # 爬虫的参数，其中params里的pn（页数）会随着遍历的改变而改变
    url = 'https://api.bilibili.com/x/v3/fav/resource/list'
    params = {
        'ps': 20,
        'keyword': '',
        'order': 'mtime',
        'type': 0,
        'tid': 0,
        'platform': 'web',
        'jsonp': 'jsonp',
        'pn': 1,
        'media_id': Media_Id
    }
    headers = {'SESSDATA' : 'xxx'}

    data = {}
    # 遍历爬取一个收藏夹的不同页数，然后合并到一个字典里
    for params['pn'] in range(MaxPage)[1::]:
        print('第' + str(params['pn']) + '页')

        response = requests.get(url=url, params=params, headers=headers).json()
        medias_list = response['data']['medias']
        # 将不同页数合并到字典里
        for i in medias_list:
            data[i['id']] = i
    return data


# 爬取全部收藏夹信息
def GetALLFavorite(WritePath):
    # 打开文件，获取之前爬取到的收藏夹id和收藏夹页数
    with open(WritePath + '收藏夹id.json', 'r', encoding='utf-8') as fp:
        file = json.load(fp)
    ID_list = file['data']['list']

    # 遍历所有收藏夹，爬取所有收藏夹
    for i in ID_list:
        print('爬取中...当前正在爬取' + i['title'])
        filename = WritePath + i['title'] + '.json'

        # 获得一个收藏夹信息，经过处理后一个json文件中
        data = GetOneFavorite(i['id'], math.ceil(i['media_count'] / 20) + 1)
        a_fav_data = CompareLastTime(filename, ProcessRawData(data))
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(a_fav_data, f, ensure_ascii=False)

    os.remove(WritePath + '收藏夹id.json')
    print('所有收藏夹爬取完毕！！！')


def SetPhotoURl(ReadPath):
    file_name_list = os.listdir(ReadPath)
    Cover_dict = {}
    Face_dict = {}
    for i in file_name_list:
        cover_url = {}  # 视频封面按收藏夹分类
        with open(ReadPath + i, 'r', encoding='utf-8') as f1:
            data = json.load(f1)
        for j in data.values():
            if j['是否失效']:
                cover_url['已失效视频'] = j['视频信息']['封面']
                print(j['视频信息']['标题'] + '已失效')
            else:
                cover_url[j['BV']] = j['视频信息']['封面']
            Face_dict[j['up主']['ID']] = j['up主']['头像']

        Cover_dict[i.split('.')[0]] = cover_url
    with open('视频封面url.json', 'w', encoding='utf-8') as fp:
        json.dump(Cover_dict, fp, ensure_ascii=False)
    with open('up头像url.json', 'w', encoding='utf-8') as fp:
        json.dump(Face_dict, fp, ensure_ascii=False)


# 爬取视频封面
def GetCover(PhotoURL_filename):
    count, MaxCount = 0, 0
    with open(PhotoURL_filename, 'r', encoding='utf-8') as fp:
        PhotoURL_dict = json.load(fp)
    for i in PhotoURL_dict.values():
        MaxCount += len(i.values())

    for fav_name in PhotoURL_dict.keys():
        url_list = []  # 放多个url进行多线程
        # 视频封面按收藏夹分类
        Cover_Path = '视频封面/' + fav_name + '/'
        if not os.path.exists(Cover_Path):
            os.makedirs(Cover_Path)
        url_list = []  # 放多个url进行多线程
        fav_count = 0
        for BV, url in PhotoURL_dict[fav_name].items():
            count += 1
            fav_count += 1
            message = '[' + str(count) + '/' + str(MaxCount) + ']:视频封面' + BV + fav_name + '[' + str(
                fav_count) + '/' + str(len(PhotoURL_dict[fav_name])) + ']'
            print(message)
            url_list.append(url)
            fs = []
            if len(url_list) == 5 or fav_count == len(PhotoURL_dict[fav_name]):
                executor = futures.ThreadPoolExecutor(max_workers=5)
                while len(url_list) != 0:
                    f = executor.submit(requests.get, url_list.pop())
                    # print(message)
                    fs.append(f)
                futures.wait(fs)
                result = [f.result().content for f in fs]
                print(fav_count)
                for i in range(len(result)):
                    with open(Cover_Path + list(PhotoURL_dict[fav_name].keys())[fav_count - 1 - i] + '.jpg',
                              'wb') as fp:
                        print(fav_count - 1 - i)
                        fp.write(result[i])


def GetFace(PhotoURL_filename):
    with open(PhotoURL_filename, 'r', encoding='utf-8') as fp:
        PhotoURL_dict = json.load(fp)
    count, MaxCount = 0, len(PhotoURL_dict)

    Face_Path = 'up头像/'
    if not os.path.exists(Face_Path):
        os.makedirs(Face_Path)

    url_list = []  # 放多个url进行多线程
    for ID, url in PhotoURL_dict.items():
        count += 1
        message = '[' + str(count) + '/' + str(MaxCount) + ']:up头像' + ID
        print(message)
        url_list.append(url)
        fs = []
        if len(url_list) == 5 or count == MaxCount:
            executor = futures.ThreadPoolExecutor(max_workers=5)
            while len(url_list) != 0:
                f = executor.submit(requests.get, url_list.pop())
                # print(message)
                fs.append(f)
            futures.wait(fs)
            result = [f.result().content for f in fs]
            for i in range(len(result)):
                with open(Face_Path + list(PhotoURL_dict.keys())[count - 1 - i] + '.jpg', 'wb') as fp:
                    fp.write(result[i])


if __name__ == "__main__":
    path1 = '收藏夹信息/'  # 存放信息的文件夹
    path2 = '视频封面/'  # 放视频封面的文件夹
    path3 = 'up头像/'  # 放up主头像的文件夹

    if not os.path.exists(path1):
        os.makedirs(path1)
    if not os.path.exists(path2):
        os.makedirs(path2)
    if not os.path.exists(path3):
        os.makedirs(path3)

    time_list = []
    STime = time.perf_counter()
    GetFavoriteID(path1, args.uid)  # 自己账号的uid
    GetALLFavorite(path1)
    SetPhotoURl(path1)
    GetCover('视频封面url.json')
    GetFace('up头像url.json')
    ETime = time.perf_counter()
    time_list.append(time.strftime("%M:%S", time.gmtime(ETime - STime)))

    STime = time.perf_counter()
    view(path1, './收藏夹信息.xlsx')
    ETime = time.perf_counter()
    time_list.append(time.strftime("%M:%S", time.gmtime(ETime - STime)))
    print('执行爬取代码所用时间：' + time_list[0])  # 视收藏视频数量和网速而定，800视频大概五分钟
    print('将数据写入excel文件所用时间' + time_list[1])  # 800视频大概两分半钟
