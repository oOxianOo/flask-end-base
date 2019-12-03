from flask import Flask
from flask import request
from flask.views import MethodView
from flask_sqlalchemy import SQLAlchemy
from flaskr.apis.ApiBase import ApiBase
from flaskr.models import User
from flaskr.token import TokenState, Token
from flaskr import redis_db, config
from flaskr.response import error_response, success_response, fail_response
from flaskr.email import is_valid_email

SECRET_KEY = config.SECRET_KEY
AUTH_TOKEN_SECONDS = 259200  # 3 天
LOGIN_REDIS_KEY_PREFIX = "login_token"

class LoginApi(ApiBase):

    @classmethod
    def register_api(cls, app: Flask):
        cls._register_api(app, "login", "/login", "token")

    def get(self, token):
        """获取登录信息

        :param token: 请求的令牌
        :return: 用户信息
        """
        info = self.check_token(token, SECRET_KEY, LOGIN_REDIS_KEY_PREFIX)
        if info.get("status") == "success":
            data = info.get("data")
            user = User.query.filter_by(id=data.get("id")).first()
            if user:
                user_data = {
                    "id": user.id,
                    "name": user.name,
                    "email": user.email
                }
                return success_response("用户信息", user_data)
            else:
                key = self.get_redis_key(LOGIN_REDIS_KEY_PREFIX, user.id)
                redis_db.delete(key)
                return fail_response("无效的令牌")
        return info

    def post(self):
        """登录账号

        :return: 登录令牌
        """
        json = request.get_json()
        valid, info = self.check_json(json, "email", "password")
        if not valid:
            return fail_response(info)
        password = json.get("password", "").strip()
        email = json.get("email", "").strip()
        user = User.query.filter_by(email=email).first()
        if user and user.verify_password(password):
            token = Token.generate_token(user.id, SECRET_KEY, AUTH_TOKEN_SECONDS)
            key = self.get_redis_key(LOGIN_REDIS_KEY_PREFIX, user.id)
            redis_db.set(key, token, AUTH_TOKEN_SECONDS)
            return success_response("登录成功", {"token": token})
        else:
            return fail_response("用户名或密码错误")

    def put(self, token):
        """更新登录信息

        :param token: 请求的令牌
        :return: 新的令牌
        """
        info = self.check_token(token, SECRET_KEY, LOGIN_REDIS_KEY_PREFIX)
        if info.get("status") == "success":
            data = info.get("data")
            key = self.get_redis_key(LOGIN_REDIS_KEY_PREFIX, data.get("id"))
            user = User.query.filter_by(id=data.get("id")).first()
            if user:
                new_token = Token.generate_token(user.id, SECRET_KEY, AUTH_TOKEN_SECONDS)
                redis_db.set(key, new_token)
                return success_response("新的令牌", {"token": new_token})
            else:
                redis_db.delete(key)
                return fail_response("无效的令牌")
        return info


class LogoutApi(ApiBase):
    redis_key_prefix = "logout_token"

    @classmethod
    def register_api(cls, app: Flask):
        cls._register_api(app, "logout", "/logout", "token")

    def delete(self, token):
        info = self.check_token(token, SECRET_KEY, LOGIN_REDIS_KEY_PREFIX)
        if info.get("status") == "success":
            data = info.get("data")
            key = self.get_redis_key(LOGIN_REDIS_KEY_PREFIX, data.get("id"))
            redis_db.delete(key)
            return success_response("退出登录")
        return info
