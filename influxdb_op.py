# -*- coding: utf-8 -*-

from influxdb_client import InfluxDBClient,Point
from influxdb_client.client.write_api import SYNCHRONOUS
from influxdb_client.domain.bucket import Bucket
from influxdb_client.domain.bucket_retention_rules import BucketRetentionRules
from datetime import datetime
import configparser

# 配置连接信息（不设置用户名和密码）
host = 'localhost'
port = 8087
database = 'reviewdb'
token = 'mf6Q0MjzJD5mWuMpt46hbcm-_BgLUBX6Jp9MFYwz12vrtIJiGsgu48CMo562AK7Gk4X0dDRPKt8c5uoSwYqqNQ=='
org = 'influxdb2'
def readInfluxDbIni():
    # 创建 ConfigParser 对象
    config = configparser.ConfigParser()
    # 读取 ini 文件
    config.read('config.ini')
    global host
    global port
    host = config.get('influxdb', 'host')
    port = config.getint('influxdb', 'port')

def insertData(product_id,user_name,svn_version,file_name,reviewcode,advise):
    readInfluxDbIni()
    # 连接到 InfluxDB
    url = f"http://{host}:{port}"
    client = InfluxDBClient(url=url, token=token, org=org)
    # 创建数据库（如果不存在）
    buckets_api = client.buckets_api()

    buckets = buckets_api.find_buckets().buckets
    bucket_exists = any(b.name == database for b in buckets)
    if not bucket_exists:
        # 设置保留策略（如果提供）
        retention_rules = []
        #if retention_days:
        #   retention_rules = [BucketRetentionRules(every_seconds=retention_days * 24 * 3600)]

        # 创建 Bucket
        bucket = Bucket(name=database, retention_rules=retention_rules,org_id="606f75dc6cfcaa0e")
        created_bucket = buckets_api.create_bucket(bucket=bucket)
    
    point = Point(product_id) \
    .tag("user_name",user_name) \
    .field("name",user_name) \
    .field("svn_version",svn_version) \
    .field("file_name",file_name) \
    .field("reviewcode",reviewcode) \
    .field("advise",advise)
    
    # 写入数据
    write_api = client.write_api(write_options=SYNCHRONOUS)
    write_api.write(bucket="reviewdb", record=point)
    # 关闭连接
    client.close()


#if __name__ == "__main__":
#  insertData("id","xiaoming","12112","main.cpp","sdfsadfsdfsf","建议")