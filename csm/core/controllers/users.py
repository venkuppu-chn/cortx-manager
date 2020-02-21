#!/usr/bin/env python3

"""
 ****************************************************************************
 Filename:          users.py
 Description:       Implementation of users views

 Creation Date:     11/21/2019
 Author:            Alexander Nogikh

 Do NOT modify or remove this copyright and confidentiality notice!
 Copyright (c) 2001 - $Date: 2015/01/14 $ Seagate Technology, LLC.
 The code contained herein is CONFIDENTIAL to Seagate Technology, LLC.
 Portions are also trade secret. Any use, duplication, derivation, distribution
 or disclosure of this code, for any reason, not expressly authorized is
 prohibited. All other rights are expressly reserved by Seagate Technology, LLC.
 ****************************************************************************
"""
import json
from marshmallow import Schema, fields, validate, validates
from marshmallow.exceptions import ValidationError
from csm.core.controllers.validators import PasswordValidator, UserNameValidator
from csm.core.blogic import const
from csm.core.controllers.view import CsmView, CsmResponse, CsmAuth
from csm.common.log import Log
from csm.common.errors import InvalidRequest


# TODO: find out about policies for names and passwords
class CsmUserCreateSchema(Schema):
    user_id = fields.Str(data_key='username', required=True,
                         validate=[UserNameValidator()])
    password = fields.Str(required=True, validate=[PasswordValidator()])
    roles = fields.List(fields.String(validate=validate.OneOf(const.CSM_USER_ROLES)))
    interfaces = fields.List(fields.String(validate=validate.OneOf(const.CSM_USER_INTERFACES)))
    temperature = fields.Str(default=None)
    language = fields.Str(default=None)
    timeout = fields.Int(default=None)


class CsmGetUsersSchema(Schema):
    offset = fields.Int(validate=validate.Range(min=0), allow_none=True,
        default=None, missing=None)
    limit = fields.Int(default=None, validate=validate.Range(min=0), missing=None)
    sort_by = fields.Str(default="user_id", missing="user_id")
    sort_dir = fields.Str(validate=validate.OneOf(['desc', 'asc']),
        missing='asc', default='asc')

@CsmView._app_routes.view("/api/v1/csm/users")
@CsmView._app_routes.view("/api/v1/user")
class CsmUsersListView(CsmView):
    def __init__(self, request):
        super(CsmUsersListView, self).__init__(request)
        self._service = self.request.app["csm_user_service"]
        self._service_dispatch = {}

    """
    GET REST implementation for fetching csm users
    """
    async def get(self):
        Log.debug(f"Handling csm users fetch request."
                  f" user_id: {self.request.session.credentials.user_id}")
        csm_schema = CsmGetUsersSchema()
        try:
            request_data = csm_schema.load(self.request.rel_url.query, unknown='EXCLUDE')
        except ValidationError as val_err:
            raise InvalidRequest(
                "Invalid Parameter for alerts", str(val_err))
        users = await self._service.get_user_list(**request_data)
        return {'users': users}

    """
    POST REST implementation for creating a csm user
    """
    async def post(self):
        Log.debug(f"Handling users post request."
                  f" user_id: {self.request.session.credentials.user_id}")

        try:
            schema = CsmUserCreateSchema()
            user_body = schema.load(await self.request.json(), unknown='EXCLUDE')
        except json.decoder.JSONDecodeError as jde:
            raise InvalidRequest(message_args="Request body missing")
        except ValidationError as val_err:
            raise InvalidRequest(f"Invalid request body: {val_err}")
        return await self._service.create_user(**user_body)

@CsmView._app_routes.view("/api/v1/csm/users/{user_id}")
@CsmView._app_routes.view("/api/v1/user/{user_id}")
class CsmUsersView(CsmView):
    def __init__(self, request):
        super(CsmUsersView, self).__init__(request)
        self._service = self.request.app["csm_user_service"]
        self._service_dispatch = {}
        self._roles_service = self.request.app["roles_service"]

    """
    GET REST implementation for csm account get request
    """
    async def get(self):
        Log.debug(f"Handling get csm account request."
                  f" user_id: {self.request.session.credentials.user_id}")
        user_id = self.request.match_info["user_id"]
        return await self._service.get_user(user_id)
    """
    DELETE REST implementation for csm account delete request
    """
    async def delete(self):
        Log.debug(f"Handling delete csm account request."
                  f" user_id: {self.request.session.credentials.user_id}")
        user_id = self.request.match_info["user_id"]
        return await self._service.delete_user(user_id)

    """
    POST PUT implementation for creating a csm user
    """
    async def put(self):
        Log.debug(f"Handling users put request."
                  f" user_id: {self.request.session.credentials.user_id}")
        user_id = self.request.match_info["user_id"]

        try:
            schema = CsmUserCreateSchema()
            user_body = schema.load(await self.request.json(), partial=True,
                unknown='EXCLUDE')
        except json.decoder.JSONDecodeError as jde:
            raise InvalidRequest(message_args="Request body missing")
        except ValidationError as val_err:
            raise InvalidRequest(f"Invalid request body: {val_err}")
        return await self._service.update_user(user_id, user_body)


@CsmView._app_routes.view("/api/v1/preboarding/user")
@CsmAuth.public
class AdminUserView(CsmView):

    STATUS_CREATED = 201
    STATUS_CONFLICT = 409

    def __init__(self, request):
        super().__init__(request)
        self._service = self.request.app["csm_user_service"]

    async def post(self):
        """
        POST REST implementation of creating a root user for preboarding
        """
        Log.debug("Creating root user")

        try:
            schema = CsmUserCreateSchema()
            user_body = schema.load(await self.request.json(), unknown='EXCLUDE')
        except json.decoder.JSONDecodeError as jde:
            raise InvalidRequest(message_args="Request body missing")
        except ValidationError as val_err:
            raise InvalidRequest(message_args=f"Invalid request body: {val_err}")

        status = self.STATUS_CREATED
        response = await self._service.create_root_user(**user_body)
        if not response:
            status = self.STATUS_CONFLICT
            response = {
                'message_id': 'root_already_exists',
                'message_text': 'Root user already exists',
                'extended_message': user_body['user_id']
            }

        # TODO: We need to return specific HTTP codes here.
        # Change this after we have proper exception hierarchy.
        return CsmResponse(response, status=status)
