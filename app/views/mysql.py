# encoding=utf8
import sys
from importlib import reload
reload(sys)

from flask import flash, get_flashed_messages, redirect, render_template, request, session, url_for, jsonify, Response, abort
from flask.json import jsonify
from app import app
from app import db
from app.models.mysql import DataSource, Project,initdb
import shutil
import json
import pandas as pd
import os
from app.utils import mkdir


#解决 list, dict 不能返回的问题
class MyResponse(Response):
    @classmethod
    def force_type(cls, response, environ=None):
        if isinstance(response, (list, dict)):
            response = jsonify(response)
        return super(Response, cls).force_type(response, environ)

app.response_class = MyResponse

#初始化表，在mysql中新建表，对已存在的表无影响
# initdb()

#得到数据源列表
@app.route('/getDataSource', methods=['GET', 'POST'])
def getDataSource():
    DSs = DataSource.query.all()
    result = []
    for i in DSs:
        result.append({"id":i.id,"name":i.file_name})
    return result

#创建项目
@app.route('/creatProject', methods=['GET', 'POST'])
def creatProject():
    if request.method == 'GET':
        projectName = request.args.get('projectName')
        dataSourceId = request.args.get('dataSourceId')
        userId =  request.args.get('userId')
    else:
        projectName = request.form.get('projectName')
        dataSourceId = request.form.get('dataSourceId')
        userId = request.form.get('userId')
    print('projectName: {}, dataSourceId: {}, userId: {}'.format(projectName, dataSourceId,userId))
    project = Project(project_name=projectName,project_address='/Users/kang/PycharmProjects/project/'+projectName,user_id = userId, dataSource_id = dataSourceId)
    db.session.add(project)

    try:
        if(not (os.path.exists('/Users/kang/PycharmProjects/project/'+projectName))):
            filters = {
                DataSource.id ==dataSourceId
            }
            DSs = DataSource.query.filter(*filters).first()
            db.session.commit()
            mkdir('/Users/kang/PycharmProjects/project/'+projectName)
            print(DSs.file_url)
            print(u'/Users/kang/PycharmProjects/project/'+projectName)
            shutil.copyfile(DSs.file_url, u'/Users/kang/PycharmProjects/project/'+projectName+'/'+DSs.file_name+'.csv')
            return getProjectList()
        else:
            return "Double name"
    except:
        return "error"

#获取项目列表
@app.route('/getProjectList', methods=['GET','POST'])
def getProjectList():
    DSs = Project.query.all()
    result = []
    for i in DSs:
        result.append({"id": i.id, "name": i.project_name})
    return result

#原始数据预览
@app.route('/rawDataPreview', methods=['GET','POST'])
def rawDataPreview():
    if request.method == 'GET':
        start = request.args.get('start')
        end = request.args.get('end')
        projectName =  request.args.get('projectName')
    else:
        start = request.form.get('start')
        end = request.form.get('end')
        projectName = request.form.get('projectName')
    print('start: {}, end: {}, projectName: {}'.format(start, end, projectName))
    try:
        filters = {
            Project.project_name == projectName
        }
        Pro = Project.query.filter(*filters).first()
        DataSourceId = Pro.dataSource_id
        filters = {
            DataSource.id == DataSourceId
        }
        Ds = DataSource.query.filter(*filters).first()
        fileUrl = Ds.file_url

    except:
        return "error"
    import csv
    # with open(fileUrl, 'r') as csvfile:
    #     reader = csv.reader(csvfile)
    #     rows = [row.decode("utf8") for row in reader]
    data = pd.read_csv(fileUrl,encoding='utf-8')
    # print(data.head())
    data2 = data[int(start):int(end)].to_json(orient='records',force_ascii=False)
    # print(data2)
    # result = []
    # for i in rows[int(start):int(end)]:
    #     info = {}.fromkeys(rows[0])
    #     for j in range(len(rows[0])):
    #         info[rows[0][j]] = i[j]
    #     result.append(info)
    # # print(rows)  # 输出所有数据
    return jsonify({'length':len(data), 'data':json.loads(data2)})

#当前数据预览
@app.route('/currentDataPreview', methods=['GET','POST'])
def currentDataPreview():
    if request.method == 'GET':
        start = request.args.get('start')
        end = request.args.get('end')
        projectName =  request.args.get('projectName')
    else:
        start = request.form.get('start')
        end = request.form.get('end')
        projectName = request.form.get('projectName')
    print('start: {}, end: {}, projectId: {}'.format(start, end, projectName))
    try:
        filters = {
            Project.project_name == projectName
        }
        Pro = Project.query.filter(*filters).first()
        ProjectAddress = Pro.project_address
        filename =''
        for root, dirs, files in os.walk(ProjectAddress):
            # print(root) #当前目录路径
            # print(dirs) #当前路径下所有子目录
            # print(files) #当前路径下所有非目录子文件
            for file in files:
                filename = file
                break
            break
    except:
        return "error"
    try:
        data = pd.read_csv(ProjectAddress+'/'+filename, encoding='utf-8')
        data2 = data[int(start):int(end)].to_json(orient='records', force_ascii=False)
        return jsonify({'length': len(data), 'data': json.loads(data2)})
    except:
        return "error read"