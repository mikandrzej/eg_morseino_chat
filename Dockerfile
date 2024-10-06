#
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
#

FROM python:alpine3.18

WORKDIR /usr/src/app

ARG SERVER_IP
ARG UDP_PORT
ARG MAX_CLIENTS
ARG KEEPALIVE
ARG TIMEOUT
ARG ACTIVITY_TIMEOUT
ARG KICKOFF_TIMEOUT
ARG ROOM_NUMBERS
ARG ROOM0_HOOK
ARG ROOM1_HOOK
ARG ROOM2_HOOK
ARG ROOM3_HOOK

COPY eg_chat_server.py ./
COPY eg_mopper.py ./
COPY requirements.txt ./

EXPOSE 7373/udp

RUN pip install -r requirements.txt

CMD [ "python", "./eg_chat_server.py"]
