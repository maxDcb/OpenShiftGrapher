import argparse
from argparse import RawTextHelpFormatter
import sys

import json
import subprocess

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

import yaml
from kubernetes import client
from openshift.dynamic import DynamicClient
from openshift.helper.userpassauth import OCPLoginConfiguration
 

##
## Input
##
parser = argparse.ArgumentParser(description=f"""Exemple:
    python3 AbsentEnum.py -a "https://api.cluster.net:6443" -t "eyJhbGciOi..."
    python3 AbsentEnum.py -a "https://api.cluster.net:6443" -t $(cat token.txt)""",
    formatter_class=RawTextHelpFormatter,)

parser.add_argument('-a', '--apiUrl', required=True, help='api url.')
parser.add_argument('-t', '--token', required=True, help='service account token.')

args = parser.parse_args()

hostApi = args.apiUrl
api_key = args.token
collector = "all"


##
## Init OC
##
print("#### Init OC ####")

kubeConfig = OCPLoginConfiguration(host=hostApi)
kubeConfig.verify_ssl = False
kubeConfig.token = api_key
kubeConfig.api_key = {"authorization": "Bearer {}".format(api_key)}

k8s_client = client.ApiClient(kubeConfig)
dyn_client = DynamicClient(k8s_client)


##
## Project
##
print("#### Project ####")

projects = dyn_client.resources.get(api_version='project.openshift.io/v1', kind='Project')
project_list = projects.get()


##
## Service account
##
print("#### Service Account ####")

serviceAccounts = dyn_client.resources.get(api_version='v1', kind='ServiceAccount')
serviceAccount_list = serviceAccounts.get()
 

##
## SSC
##
print("#### SSC ####")

SSCs = dyn_client.resources.get(api_version='security.openshift.io/v1', kind='SecurityContextConstraints')
SSC_list = SSCs.get()
 

##
## SSC Binding
## 
print("#### SSC Binding ####")

if "all" in collector or "scc" in collector:
    for enum in SSC_list.items:
        # print(enum.metadata)
        process = subprocess.run(["oc", "--token={}".format(api_key), "adm", "policy", "who-can", "use", "scc", enum.metadata.name, "-A"], check=True, stdout=subprocess.PIPE, universal_newlines=True)
        info = process.stdout
        for line in info.split('\n'):
            if "system:serviceaccount:" in line:
                test = line.split(":")
                subjectNamespace = test[2]
                subjectName = test[3]

                try:
                    serviceAccount = serviceAccounts.get(name=subjectName, namespace=subjectNamespace)
                except: 
                    print("[o] serviceAccount related to SSC: ", enum.metadata.name ,", don't exist: ", subjectNamespace, ":", subjectName, sep='')    

                try:
                    project_list = projects.get(name=subjectNamespace)

                except: 
                    print("[+] serviceAccount and project related to SSC: ", enum.metadata.name ,", don't exist: ", subjectNamespace, ":", subjectName, sep='')       


##
## Role
## 
print("#### Role ####")

roles = dyn_client.resources.get(api_version='rbac.authorization.k8s.io/v1', kind='Role')
role_list = roles.get()
 

##
## ClusterRole
## 
print("#### ClusterRole ####")

clusterroles = dyn_client.resources.get(api_version='rbac.authorization.k8s.io/v1', kind='ClusterRole')
clusterrole_list = clusterroles.get()
 

##
## RoleBinding
## 
print("#### RoleBinding ####")

roleBindings = dyn_client.resources.get(api_version='rbac.authorization.k8s.io/v1', kind='RoleBinding')
roleBinding_list = roleBindings.get()

if "all" in collector or "role" in collector:
    for enum in roleBinding_list.items:
        # print(enum)
        description = enum.description
        if description:
            ok=1
        else:
            description = ""

        roleKind = enum.roleRef.kind
        roleName = enum.roleRef.name

        if enum.subjects:
            for subject in enum.subjects:
                subjectKind = subject.kind
                subjectName = subject.name
                subjectNamespace = subject.namespace

                if subjectKind == "ServiceAccount": 
                    if subjectNamespace:
                        try:
                            serviceAccount = serviceAccounts.get(name=subjectName, namespace=subjectNamespace)

                        except: 
                            print("[o] serviceAccount related to Role: ", roleName ,", don't exist: ", subjectNamespace, ":", subjectName, sep='')

                        try:
                            project_list = projects.get(name=subjectNamespace)

                        except: 
                            print("[+] serviceAccount and project related to Role: ", roleName ,", don't exist: ", subjectNamespace, ":", subjectName, sep='')
                                

##
## ClusterRoleBinding
## 
print("#### ClusterRoleBinding ####")

clusterRoleBindings = dyn_client.resources.get(api_version='rbac.authorization.k8s.io/v1', kind='ClusterRoleBinding')
clusterRoleBinding_list = clusterRoleBindings.get()
 
if "all" in collector or "clusterrole" in collector:
    for enum in clusterRoleBinding_list.items:
        # print(enum)
        description = enum.description
        if description:
            ok=1
        else:
            description = ""

        roleKind = enum.roleRef.kind
        roleName = enum.roleRef.name

        if enum.subjects:
            for subject in enum.subjects:
                subjectKind = subject.kind
                subjectName = subject.name
                subjectNamespace = subject.namespace

                if subjectKind == "ServiceAccount": 
                    if subjectNamespace:
                        
                        try:
                            serviceAccount = serviceAccounts.get(name=subjectName, namespace=subjectNamespace)

                        except: 
                            print("[o] serviceAccount related to ClusterRole: ", roleName ,", don't exist: ", subjectNamespace, ":", subjectName, sep='')

                        try:
                            project_list = projects.get(name=subjectNamespace)

                        except: 
                            print("[+] serviceAccount and project related to ClusterRole: ", roleName ,", don't exist: ", subjectNamespace, ":", subjectName, sep='')
