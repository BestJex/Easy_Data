# -*- coding: UTF-8 -*-
"""
二分类
"""
from pyspark.mllib.classification import SVMModel
from pyspark.mllib.regression import LabeledPoint
import app.dao.OperatorDao as OperatorDao
from app.Utils import *
from pyspark.ml.linalg import Vectors
from pyspark.sql.types import Row
from pyspark.ml.classification import GBTClassificationModel, LogisticRegressionModel, \
    MultilayerPerceptronClassificationModel


def ml_predict(spark_session, operator_id, file_urls, condition):
    """
    机器学习模型预测函数
    :param spark_session:
    :param operator_id:
    :param file_urls: ["modelUrl","predictDataUrl"]
    # 两个输入源 一个是模型 一个是预测数据
    :param condition:
    :return:
    """
    try:
        # 修改计算状态
        OperatorDao.update_operator_by_id(operator_id, 'running', '', '')
        # 读取数据
        for url in file_urls:
            print("------fileUrl:", file_urls)
            if url[-4:] == ".csv":
                url1 = url
            else:
                url0 = url
        df = read_data(spark_session, url1)
        # 预测函数
        result_df = ml_predict_core(spark_session, operator_id, df, url0, condition)
        if isinstance(result_df, str):
            OperatorDao.update_operator_by_id(operator_id, 'error', '', result_df)
        else:
            # 存储结果
            result_df.show()
            result_file_url = save_data(result_df)
            run_info = '预测算子执行成功'
            # 修改计算状态
            OperatorDao.update_operator_by_id(operator_id, 'success', result_file_url, run_info)
            return [result_file_url]

    except Exception as e:
        run_info = str(e)
        OperatorDao.update_operator_by_id(operator_id, 'error', '', run_info)
        traceback.print_exc()
    return []


def ml_predict_core(spark_session, operator_id, df, model_url, condition):
    """
    路由控制加载哪种模型进行预测
    :param spark_session:
    :param operator_id:
    :param df:
    :param model_url:
    :param condition:
    :return:  预测结果 sparkframe
    """

    # 父节点是什么组件
    operator = OperatorDao.get_operator_by_id(operator_id)
    father_ids = operator.father_operator_ids.split(',')
    print("**********", operator.father_operator_ids)
    for father_id in father_ids:
        father = OperatorDao.get_operator_by_id(father_id)
        print("***************", father.operator_type_id)
        print("---------------", father.operator_type_id == 6001)
        operator_type_flag = father.operator_type_id

        # 模型加载节点
        if operator_type_flag == 8000:
            operator_type_flag = json.loads(father.operator_config)['parameter']['modelTypeId']

        if operator_type_flag == 6001:  # svm二分类
            prediction_df = svm_second_predict(spark_session, model_url, df, condition)
        elif operator_type_flag == 6002:  # gbdt二分类
            prediction_df = gbdt_second_predict(model_url, df, condition)
        elif operator_type_flag == 6003:  # lr二分类
            prediction_df = lr_second_predict(model_url, df, condition)
        elif operator_type_flag == 6004:  # lr多分类
            prediction_df = lr_multiple_predict(model_url, df, condition)
        elif operator_type_flag == 6005:  # mpc多分类
            prediction_df = mpc_multiple_predict(model_url, df, condition)

    # 根据父组件的类型决定加载哪种模型
    return prediction_df


def svm_second_predict(spark_session, svm_model_path, df, condition):
    """
    支持向量机二分类预测
    :param spark_session: spark 会话
    :param svm_model_path: 模型地址
    :param df: 数据
    :param condition: {"features": [12, 13, 14, 15], "label": "label"}
    特征列
    :return: 预测结果 sparkframe
    """
    feature_indexs = condition['features']
    label_index = condition['label']
    if label_index is None or label_index == "":  # 无标签列
        # 1. 准备数据
        def func(x):
            features_data = []
            for feature in feature_indexs:
                features_data.append(x[feature])
            return features_data

        predict_data = df.rdd.map(lambda x: func(x))
        print(predict_data.take(10))

        # 2.加载模型
        svm_model = SVMModel.load(spark_session.sparkContext, svm_model_path)

        # 3.预测
        def f(x):
            return {"prediction_result": x}

        prediction_rdd = svm_model.predict(predict_data)
        print(prediction_rdd.take(10))
        prediction_df = prediction_rdd.map(lambda x: Row(**f(x))).toDF()
        return prediction_df
    else:  # 有标签列
        # 1. 准备数据
        def func(x):
            features_data = []
            for feature in feature_indexs:
                features_data.append(x[feature])
            return LabeledPoint(label=x[label_index], features=features_data)

        predict_label_data = df.rdd.map(lambda x: func(x))
        print(predict_label_data.take(10))

        # 2.加载模型
        svm_model = SVMModel.load(spark_session.sparkContext, svm_model_path)

        # 3.预测
        from pyspark.sql.types import Row

        def f(x):
            return {"prediction_result": x[0], label_index: x[1]}

        prediction_rdd = predict_label_data.map(lambda x: (svm_model.predict(x.features), x.label))
        print(prediction_rdd.take(10))
        prediction_df = prediction_rdd.map(lambda x: Row(**f(x))).toDF()
        return prediction_df


def gbdt_second_predict(gbdt_model_path, df, condition):
    """
    gbdt二分类预测
    :param gbdt_model_path: 模型地址
    :param df: 数据
    :param condition: {"features": [12, 13, 14, 15], "label": "label"}
    特征列
    :return: 预测结果 sparkframe
    """
    feature_indexs = condition['features']
    label_index = condition['label']

    if label_index is None or label_index == "":  # 无标签列
        # 1. 准备数据
        def func(x):
            features_data = []
            for feature in feature_indexs:
                features_data.append(x[feature])
            return Row(features=Vectors.dense(features_data))

        training_set = df.rdd.map(lambda x: func(x)).toDF()

        # 2.加载模型
        gbdt_model = GBTClassificationModel.load(gbdt_model_path)

        # 3.预测
        prediction_df = gbdt_model.transform(training_set).select("prediction", "features")
        return prediction_df
    else:  # 有标签列
        # 1. 准备数据
        def func(x):
            features_data = []
            for feature in feature_indexs:
                features_data.append(x[feature])
            return Row(label=x[label_index], features=Vectors.dense(features_data))

        training_set = df.rdd.map(lambda x: func(x)).toDF()

        # 2.加载模型
        print("****gbdt_model_path:", gbdt_model_path)
        gbdt_model = GBTClassificationModel.load(gbdt_model_path)

        # 3.预测
        prediction_df = gbdt_model.transform(training_set).select("prediction", "label", "features")
        return prediction_df


def lr_second_predict(lr_model_path, df, condition):
    """
    lr二分类预测
    :param lr_model_path: 模型地址
    :param df: 数据
    :param condition: {"features": [12, 13, 14, 15], "label": "label"}
    特征列
    :return: 预测结果 spark dataframe
    """
    feature_indexs = condition['features']
    label_index = condition['label']

    if label_index is None or label_index == "":  # 无标签列
        # 1. 准备数据
        def func(x):
            features_data = []
            for feature in feature_indexs:
                features_data.append(x[feature])
            return Row(features=Vectors.dense(features_data))

        training_set = df.rdd.map(lambda x: func(x)).toDF()

        # 2.加载模型
        lr_model = LogisticRegressionModel.load(lr_model_path)

        # 3.预测
        prediction_df = lr_model.transform(training_set).select("prediction", "features")
        return prediction_df
    else:  # 有标签列
        # 1. 准备数据
        def func(x):
            features_data = []
            for feature in feature_indexs:
                features_data.append(x[feature])
            return Row(label=x[label_index], features=Vectors.dense(features_data))

        training_set = df.rdd.map(lambda x: func(x)).toDF()

        # 2.加载模型
        print("*****lr_model_path:", lr_model_path)
        lr_model = LogisticRegressionModel.load(lr_model_path)

        # 3.预测
        prediction_df = lr_model.transform(training_set).select("prediction", "label", "features")
        return prediction_df


""" 多分类 """


def lr_multiple_predict(lr_model_path, df, condition):
    """
    lr多分类预测
    :param lr_model_path: 模型地址
    :param df: 数据
    :param condition: {"features": [12, 13, 14, 15], "label": "label"}
    特征列
    :return: 预测结果 sparkframe
    """
    return lr_second_predict(lr_model_path, df, condition)


def mpc_multiple_predict(mpc_model_path, df, condition):
    """
    mpc多分类预测
    :param mpc_model_path: 模型地址
    :param df: 数据
    :param condition: {"features": [12, 13, 14, 15], "label": "label"}
    特征列
    :return: 预测结果 sparkframe
    """
    feature_indexs = condition['features']
    label_index = condition['label']

    if label_index is None or label_index == "":  # 无标签列
        # 1. 准备数据
        def func(x):
            features_data = []
            for feature in feature_indexs:
                features_data.append(x[feature])
            return Row(features=Vectors.dense(features_data))

        training_set = df.rdd.map(lambda x: func(x)).toDF()

        # 2.加载模型
        mpc_model = MultilayerPerceptronClassificationModel.load(mpc_model_path)

        # 3.预测
        prediction_df = mpc_model.transform(training_set).select("prediction", "features")
        return prediction_df
    else:  # 有标签列
        # 1. 准备数据
        def func(x):
            features_data = []
            for feature in feature_indexs:
                features_data.append(x[feature])
            return Row(label=x[label_index], features=Vectors.dense(features_data))

        training_set = df.rdd.map(lambda x: func(x)).toDF()

        # 2.加载模型
        print("*****mpc_model_path:", mpc_model_path)
        mpc_model = MultilayerPerceptronClassificationModel.load(mpc_model_path)

        # 3.预测
        prediction_df = mpc_model.transform(training_set).select("prediction", "label", "features")
        return prediction_df
