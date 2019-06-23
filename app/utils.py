# -*- coding: UTF-8 -*-
from app.models.mysql import Project, ProcessFlow
import os, json
from app import db
from pyspark.sql import SparkSession

# 获取一个新的SparkSession
def getSparkSession(userId, computationName):
    ss = SparkSession \
        .builder \
        .master("local") \
        .config("spark.some.config.option", "some-value") \
        .getOrCreate()
    return ss
# 返回前nums条数据（json格式）
def dfToJson(df, nums):
    data_1 = df.limit(nums).toJSON().collect()
    data_2 = ",".join(data_1)
    data_3 = '[' + data_2 + ']'
    return json.loads(data_3)

# 获取处理流
def getProcessFlowByProjectId(projectId):
    try:
        filters = {
            ProcessFlow.project_id == projectId,
        }
        return ProcessFlow.query.filter(*filters).first()
    except:
        return "error"

# 追加处理流程记录
def addProcessingFlow(projectName, userId, operateType, operateParameter):
    try:
        operate = {}
        operate['type'] = operateType
        operate['operate'] = operateParameter
        print("追加处理流程", projectName, userId, operate)
        pflow = db.session.query(ProcessFlow.id,ProcessFlow.project_id,ProcessFlow.operates). \
            join(Project, Project.id == ProcessFlow.project_id). \
            filter(Project.project_name == projectName). \
            filter(Project.user_id == userId).\
            first()
        # print(pflow)
        operates = json.loads(pflow[2])
        operates.append(operate)
        # print('operates=', operates)
        operateStr = json.dumps(operates, ensure_ascii=False)
        # print('operateStr=', operateStr)
        filters = {
            ProcessFlow.id == pflow[0],
        }
        result = ProcessFlow.query.filter(*filters).first()
        result.operates = operateStr
        db.session.commit()
    except:
        return "error"
# addProcessingFlow('甜点销售数据预处理',1,{'type':'1','operate':'列名一,关系,值,组合关系;列名一,关系,值,'})

# 获取项目
def getProjectByNameAndUserId(projectName,userId):
    try:
        print('projectName=',projectName,' userId=',userId)
        return db.session.query(Project).filter(Project.project_name == projectName) \
            .filter(Project.user_id == userId)\
            .first()
    except:
        return "error"

# 获取项目的正在操作的数据文件地址
def getProjectCurrentDataUrl(projectName):
    try:
        filters = {
            Project.project_name == projectName
        }
        Pro = Project.query.filter(*filters).first()
        ProjectAddress = Pro.project_address
        filename = ''
        for root, dirs, files in os.walk(ProjectAddress):
            # print(root) #当前目录路径
            # print(dirs) #当前路径下所有子目录
            # print(files) #当前路径下所有非目录子文件
            for file in files:
                if file[-4:] =='.csv':
                    filename = file
                    break
            break
        # print(filename)
        if filename == '':
            return "error"
        else:
            # return {'fileUrl': ProjectAddress+'/'+filename, 'projectAddress': ProjectAddress}
            return {'fileUrl': 'file://' + ProjectAddress+'/'+filename, 'projectAddress': ProjectAddress}
    except:
        return "error"
# 获取项目的正在操作的文件数据
def getProjectCurrentData(ss, projectName):
    # 解析项目路径，读取csv
    urls = getProjectCurrentDataUrl(projectName)
    if urls == 'error':
        return "error: 项目名或项目路径有误"  # 错误类型：项目名或项目路径有误
    fileUrl = urls['fileUrl']
    df = ss.read.csv(fileUrl, header=True, inferSchema=True)
    return df

#根据指定路径创建文件夹
def mkdir(path):
    # 引入模块
    import os

    # 去除首位空格
    path=path.strip()
    # 去除尾部 \ 符号
    path=path.rstrip("\\")

    # 判断路径是否存在
    # 存在     True
    # 不存在   False
    isExists=os.path.exists(path)

    # 判断结果
    if not isExists:
        # 如果不存在则创建目录
        print(path+' 创建成功')
        # 创建目录操作函数
        os.makedirs(path)
        return True
    else:
        # 如果目录存在则不创建，并提示目录已存在
        print(path+' 目录已存在')
        return False

def deldir(path):
    import os
    if os.path.exists(path):
        #删除文件，可使用以下两种方法。
        os.remove(path)
        return True
    else:
        print('no such file:%s' % path)
        return False


def is_number(s):
    try:
        float(s)
        return True
    except ValueError:
        pass

    try:
        import unicodedata
        unicodedata.numeric(s)
        return True
    except (TypeError, ValueError):
        pass
    return False
