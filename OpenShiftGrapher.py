import argparse
from argparse import RawTextHelpFormatter
import sys
import os

import json
import subprocess

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from py2neo import Graph, Node, Relationship

import yaml
from kubernetes import client
from openshift.dynamic import DynamicClient
from openshift.helper.userpassauth import OCPLoginConfiguration
 

##
## Input
##
parser = argparse.ArgumentParser(description=f"""Exemple:
    python3 GenClusterGraph.py -a "https://api.cluster.net:6443" -t "eyJhbGciOi..."
    python3 GenClusterGraph.py -a "https://api.cluster.net:6443" -t $(cat token.txt)
    python3 GenClusterGraph.py -a "https://api.cluster.net:6443" -t $(cat token.txt) -c scc role route""",
    formatter_class=RawTextHelpFormatter,)

parser.add_argument('-r', '--resetDB', action="store_true", help='reset the neo4j db.')
parser.add_argument('-a', '--apiUrl', required=True, help='api url.')
parser.add_argument('-t', '--token', required=True, help='service account token.')
parser.add_argument('-c', '--collector', nargs="+", default=[], help='list of collectors. Possible values: all, project, scc, sa, role, clusterrole, rolebinding, clusterrolebinding, route, pod ')
parser.add_argument('-u', '--userNeo4j', default="neo4j", help='neo4j database user.')
parser.add_argument('-p', '--passwordNeo4j', default="rootroot", help='neo4j database password.')

args = parser.parse_args()

hostApi = args.apiUrl
api_key = args.token
resetDB = args.resetDB
userNeo4j = args.userNeo4j
passwordNeo4j = args.passwordNeo4j
collector = args.collector

release = True


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
## Init neo4j
##
print("#### Init neo4j ####")

graph = Graph("bolt://localhost:7687", user=userNeo4j, password=passwordNeo4j)
if resetDB:
    if input("are you sure your want to reset the db? (y/n)") != "y":
        exit()
    graph.delete_all()


##
## Project
##
print("#### Project ####")

projects = dyn_client.resources.get(api_version='project.openshift.io/v1', kind='Project')
project_list = projects.get()

if "all" in collector or "project" in collector:
    for enum in project_list.items:
        # print(enum.metadata)
        try:
            tx = graph.begin()
            a = Node("Project", name=enum.metadata.name, uid=enum.metadata.uid)
            a.__primarylabel__ = "Project"
            a.__primarykey__ = "uid"
            node = tx.merge(a) 
            graph.commit(tx)
        except Exception as e: 
            if release:
                print(e)
                pass
            else:
                exc_type, exc_obj, exc_tb = sys.exc_info()
                fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                print(exc_type, fname, exc_tb.tb_lineno)
                print("Error:", e)
                sys.exit(1)


##
## Service account
##
print("#### Service Account ####")

serviceAccounts = dyn_client.resources.get(api_version='v1', kind='ServiceAccount')
serviceAccount_list = serviceAccounts.get()
 
if "all" in collector or "sa" in collector:
    for enum in serviceAccount_list.items:
        # print(enum.metadata)
        try:
            tx = graph.begin()
            a = Node("ServiceAccount", name=enum.metadata.name, namespace=enum.metadata.namespace, uid=enum.metadata.uid)
            a.__primarylabel__ = "ServiceAccount"
            a.__primarykey__ = "uid"

            try:
                project_list = projects.get(name=enum.metadata.namespace)
                projectNode = Node("Project",name=project_list.metadata.name, uid=project_list.metadata.uid)
                projectNode.__primarylabel__ = "Project"
                projectNode.__primarykey__ = "uid"

            except: 
                uid = enum.metadata.namespace
                projectNode = Node("AbsentProject", name=enum.metadata.namespace, uid=uid)
                projectNode.__primarylabel__ = "AbsentProject"
                projectNode.__primarykey__ = "uid"


            r2 = Relationship(projectNode, "CONTAIN SA", a)

            node = tx.merge(a) 
            node = tx.merge(projectNode) 
            node = tx.merge(r2) 
            graph.commit(tx)

        except Exception as e: 
            if release:
                print(e)
                pass
            else:
                exc_type, exc_obj, exc_tb = sys.exc_info()
                fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                print(exc_type, fname, exc_tb.tb_lineno)
                print("Error:", e)
                sys.exit(1)


##
## SSC
##
print("#### SSC ####")

SSCs = dyn_client.resources.get(api_version='security.openshift.io/v1', kind='SecurityContextConstraints')
SSC_list = SSCs.get()
 
if "all" in collector or "scc" in collector:
    for enum in SSC_list.items:
        
        try:
            tx = graph.begin()
            a = Node("SCC",name=enum.metadata.name, uid=enum.metadata.uid)
            a.__primarylabel__ = "SCC"
            a.__primarykey__ = "uid"
            node = tx.merge(a) 
            graph.commit(tx)

        except Exception as e: 
            if release:
                print(e)
                pass
            else:
                exc_type, exc_obj, exc_tb = sys.exc_info()
                fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                print(exc_type, fname, exc_tb.tb_lineno)
                print("Error:", e)
                sys.exit(1)



# ##
# ## SSC Binding
# ## 
# print("#### SSC Binding ####")

# if "all" in collector or "scc" in collector:
#     for enum in SSC_list.items:
#         # print(enum.metadata)
#         process = subprocess.run(["oc", "--token={}".format(api_key), "adm", "policy", "who-can", "use", "scc", enum.metadata.name, "-A"], check=True, stdout=subprocess.PIPE, universal_newlines=True)
#         info = process.stdout
#         for line in info.split('\n'):
#             if "system:serviceaccount:" in line:
#                 test = line.split(":")
#                 subjectNamespace = test[2]
#                 subjectName = test[3]

#                 try:
#                     serviceAccount = serviceAccounts.get(name=subjectName, namespace=subjectNamespace)
#                     subjectNode = Node("ServiceAccount",name=serviceAccount.metadata.name, namespace=serviceAccount.metadata.namespace, uid=serviceAccount.metadata.uid)
#                     subjectNode.__primarylabel__ = "ServiceAccount"
#                     subjectNode.__primarykey__ = "uid"
#                 except: 
#                     uid = subjectName+"_"+subjectNamespace
#                     subjectNode = Node("AbsentServiceAccount", name=subjectName, namespace=subjectNamespace, uid=uid)
#                     subjectNode.__primarylabel__ = "AbsentServiceAccount"
#                     subjectNode.__primarykey__ = "uid"  
#                     # print("!!!! serviceAccount related to SSC: ", enum.metadata.name ,", don't exist: ", subjectNamespace, ":", subjectName, sep='')    

#                 try:
#                     project_list = projects.get(name=subjectNamespace)
#                     projectNode = Node("Project",name=project_list.metadata.name, uid=project_list.metadata.uid)
#                     projectNode.__primarylabel__ = "Project"
#                     projectNode.__primarykey__ = "uid"

#                 except: 
#                     uid = subjectNamespace
#                     projectNode = Node("AbsentProject",name=subjectNamespace, uid=uid)
#                     projectNode.__primarylabel__ = "AbsentProject"
#                     projectNode.__primarykey__ = "uid"      

#                 tx = graph.begin()
#                 a = Node("SCC",name=enum.metadata.name, uid=enum.metadata.uid)
#                 a.__primarylabel__ = "SCC"
#                 a.__primarykey__ = "uid"
#                 r1 = Relationship(projectNode, "CONTAIN SA", subjectNode)
#                 r2 = Relationship(subjectNode, "CAN USE SCC", a)
#                 node = tx.merge(projectNode) 
#                 node = tx.merge(subjectNode) 
#                 node = tx.merge(a) 
#                 node = tx.merge(r2) 
#                 graph.commit(tx)


##
## Role
## 
print("#### Role ####")

roles = dyn_client.resources.get(api_version='rbac.authorization.k8s.io/v1', kind='Role')
role_list = roles.get()
 
if "all" in collector or "role" in collector:
    for role in role_list.items:
        # print(role.metadata)

        roleNode = Node("Role",name=role.metadata.name, namespace=role.metadata.namespace, uid=role.metadata.uid)
        roleNode.__primarylabel__ = "Role"
        roleNode.__primarykey__ = "uid"

        try:
            tx = graph.begin()
            node = tx.merge(roleNode) 
            graph.commit(tx)
        except Exception as e: 
            if release:
                print(e)
                pass
            else:
                exc_type, exc_obj, exc_tb = sys.exc_info()
                fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                print(exc_type, fname, exc_tb.tb_lineno)
                print("Error:", e)
                sys.exit(1)

        if role.rules:
            for rule in role.rules:
                if rule.apiGroups:
                    for apiGroup in rule.apiGroups:
                        for resource in rule.resources:
                            if resource == "securitycontextconstraints":
                                if rule.resourceNames:
                                    for resourceName in rule.resourceNames:

                                        try:
                                            SSC_list = SSCs.get(name=resourceName)
                                            sscNode = Node("SCC", name=SSC_list.metadata.name, uid=SSC_list.metadata.uid)
                                            sscNode.__primarylabel__ = "SCC"
                                            sscNode.__primarykey__ = "uid"
                                        except: 
                                            uid = "SCC_"+resourceName
                                            sscNode = Node("AbsentSCC", name=resourceName, uid=uid)
                                            sscNode.__primarylabel__ = "AbsentSCC"
                                            sscNode.__primarykey__ = "uid"

                                        try:
                                            tx = graph.begin()
                                            r1 = Relationship(roleNode, "CAN USE SCC", sscNode)
                                            node = tx.merge(roleNode) 
                                            node = tx.merge(sscNode) 
                                            node = tx.merge(r1) 
                                            graph.commit(tx)

                                        except Exception as e: 
                                            if release:
                                                print(e)
                                                pass
                                            else:
                                                exc_type, exc_obj, exc_tb = sys.exc_info()
                                                fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                                                print(exc_type, fname, exc_tb.tb_lineno)
                                                print("Error:", e)
                                                sys.exit(1)

                            else:
                                for verb in rule.verbs:

                                    if apiGroup == "":
                                        resourceName = resource
                                    else:
                                        resourceName = apiGroup
                                        resourceName = ":"
                                        resourceName = resource

                                    uid="Resource_"+role.metadata.namespace+"_"+resourceName
                                    ressourceNode = Node("Resource", name=resourceName, uid=uid)
                                    ressourceNode.__primarylabel__ = "Resource"
                                    ressourceNode.__primarykey__ = "uid"

                                    try:
                                        tx = graph.begin()
                                        if verb == "impersonate":
                                            r1 = Relationship(roleNode, "impers", ressourceNode)  
                                        else:
                                            r1 = Relationship(roleNode, verb, ressourceNode)
                                        node = tx.merge(roleNode) 
                                        node = tx.merge(ressourceNode) 
                                        node = tx.merge(r1) 
                                        graph.commit(tx)

                                    except Exception as e: 
                                        if release:
                                            print(e)
                                            pass
                                        else:
                                            exc_type, exc_obj, exc_tb = sys.exc_info()
                                            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                                            print(exc_type, fname, exc_tb.tb_lineno)
                                            print("Error:", e)
                                            sys.exit(1)

                if rule.nonResourceURLs: 
                    for nonResourceURL in rule.nonResourceURLs: 
                        for verb in rule.verbs:

                            uid="ResourceNoUrl_"+role.metadata.namespace+"_"+nonResourceURL
                            ressourceNode = Node("ResourceNoUrl", name=nonResourceURL, uid=uid)
                            ressourceNode.__primarylabel__ = "ResourceNoUrl"
                            ressourceNode.__primarykey__ = "uid"

                            try:
                                tx = graph.begin()
                                r1 = Relationship(roleNode, verb, ressourceNode)
                                node = tx.merge(roleNode) 
                                node = tx.merge(ressourceNode) 
                                node = tx.merge(r1) 
                                graph.commit(tx)

                            except Exception as e: 
                                if release:
                                    print(e)
                                    pass
                                else:
                                    exc_type, exc_obj, exc_tb = sys.exc_info()
                                    fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                                    print(exc_type, fname, exc_tb.tb_lineno)
                                    print("Error:", e)
                                    sys.exit(1)


##
## ClusterRole
## 
print("#### ClusterRole ####")

clusterroles = dyn_client.resources.get(api_version='rbac.authorization.k8s.io/v1', kind='ClusterRole')
clusterrole_list = clusterroles.get()
 
if "all" in collector or "clusterrole" in collector:
    nbObject = len(clusterrole_list.items)
    progress = 0.0
    for role in clusterrole_list.items:
        progress=progress+1
        print("ClusterRole progress = {}%".format(progress/nbObject*100.0))

        try:
            tx = graph.begin()
            roleNode = Node("ClusterRole", name=role.metadata.name, uid=role.metadata.uid)
            roleNode.__primarylabel__ = "ClusterRole"
            roleNode.__primarykey__ = "uid"
            node = tx.merge(roleNode) 
            graph.commit(tx)

        except Exception as e: 
            if release:
                print(e)
                pass
            else:
                exc_type, exc_obj, exc_tb = sys.exc_info()
                fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                print(exc_type, fname, exc_tb.tb_lineno)
                print("Error:", e)
                sys.exit(1)

        if role.rules:
            for rule in role.rules:
                if rule.apiGroups:
                    for apiGroup in rule.apiGroups:
                        for resource in rule.resources:
                            if resource == "securitycontextconstraints":
                                if rule.resourceNames:
                                    for resourceName in rule.resourceNames:

                                        try:
                                            SSC_list = SSCs.get(name=resourceName)
                                            sscNode = Node("SCC", name=SSC_list.metadata.name, uid=SSC_list.metadata.uid)
                                            sscNode.__primarylabel__ = "SCC"
                                            sscNode.__primarykey__ = "uid"
                                        except: 
                                            uid = "SCC_"+resourceName
                                            sscNode = Node("AbsentSCC", name=resourceName, uid=uid)
                                            sscNode.__primarylabel__ = "AbsentSCC"
                                            sscNode.__primarykey__ = "uid"

                                        try:
                                            tx = graph.begin()
                                            r1 = Relationship(roleNode, "CAN USE SCC", sscNode)
                                            node = tx.merge(roleNode) 
                                            node = tx.merge(sscNode) 
                                            node = tx.merge(r1) 
                                            graph.commit(tx)

                                        except Exception as e: 
                                            if release:
                                                print(e)
                                                pass
                                            else:
                                                exc_type, exc_obj, exc_tb = sys.exc_info()
                                                fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                                                print(exc_type, fname, exc_tb.tb_lineno)
                                                print("Error:", e)
                                                sys.exit(1)

                            else:
                                for verb in rule.verbs:

                                    if apiGroup == "":
                                        resourceName = resource
                                    else:
                                        resourceName = apiGroup
                                        resourceName = ":"
                                        resourceName = resource

                                    uid="Resource_cluster"+"_"+resourceName
                                    ressourceNode = Node("Resource", name=resourceName, uid=uid)
                                    ressourceNode.__primarylabel__ = "Resource"
                                    ressourceNode.__primarykey__ = "uid"

                                    try:
                                        tx = graph.begin()
                                        if verb == "impersonate":
                                            r1 = Relationship(roleNode, "impers", ressourceNode)  
                                        else:
                                            r1 = Relationship(roleNode, verb, ressourceNode)
                                        node = tx.merge(roleNode) 
                                        node = tx.merge(ressourceNode) 
                                        node = tx.merge(r1) 
                                        graph.commit(tx)

                                    except Exception as e: 
                                        if release:
                                            print(e)
                                            pass
                                        else:
                                            exc_type, exc_obj, exc_tb = sys.exc_info()
                                            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                                            print(exc_type, fname, exc_tb.tb_lineno)
                                            print("Error:", e)
                                            sys.exit(1)

                if rule.nonResourceURLs: 
                    for nonResourceURL in rule.nonResourceURLs: 
                        for verb in rule.verbs:

                            uid="ResourceNoUrl_cluster"+"_"+nonResourceURL
                            ressourceNode = Node("ResourceNoUrl", name=nonResourceURL, uid=uid)
                            ressourceNode.__primarylabel__ = "ResourceNoUrl"
                            ressourceNode.__primarykey__ = "uid"

                            try:
                                tx = graph.begin()
                                r1 = Relationship(roleNode, verb, ressourceNode)
                                node = tx.merge(roleNode) 
                                node = tx.merge(ressourceNode) 
                                node = tx.merge(r1) 
                                graph.commit(tx)

                            except Exception as e: 
                                if release:
                                    print(e)
                                    pass
                                else:
                                    exc_type, exc_obj, exc_tb = sys.exc_info()
                                    fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                                    print(exc_type, fname, exc_tb.tb_lineno)
                                    print("Error:", e)
                                    sys.exit(1)


##
## User
## 
print("#### User ####")

users = dyn_client.resources.get(api_version='v1', kind='User')
user_list = users.get()

# if "all" in collector or "pod" in collector:
if "all" in collector or "user" in collector:
    for enum in user_list.items:

        name = enum.metadata.name
        uid = enum.metadata.uid

        userNode = Node("User", name=name, uid=uid)
        userNode.__primarylabel__ = "User"
        userNode.__primarykey__ = "uid"

        try:
            tx = graph.begin()
            node = tx.merge(userNode) 
            graph.commit(tx)

        except Exception as e: 
            if release:
                print(e)
                pass
            else:
                exc_type, exc_obj, exc_tb = sys.exc_info()
                fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                print(exc_type, fname, exc_tb.tb_lineno)
                print("Error:", e)
                sys.exit(1)

##
## Group
## 
print("#### Group ####")

groups = dyn_client.resources.get(api_version='v1', kind='Group')
group_list = groups.get()

# if "all" in collector or "pod" in collector:
if "all" in collector or "group" in collector:
    nbObject = len(group_list.items)
    progress = 0.0
    for enum in group_list.items:
        progress=progress+1
        print("Group progress = {}%".format(progress/nbObject*100.0))

        name = enum.metadata.name
        uid = enum.metadata.uid
        userNames = enum.users

        if userNames:
            for user in userNames:
                groupNode = Node("Group", name=name, uid=uid)
                groupNode.__primarylabel__ = "Group"
                groupNode.__primarykey__ = "uid"

                try:
                    user_list = users.get(name=user)
                    # print(user_list)
                    userNode = Node("User", name=user_list.metadata.name, uid=user_list.metadata.uid)
                    userNode.__primarylabel__ = "User"
                    userNode.__primarykey__ = "uid"
                except: 
                    uid = user
                    userNode = Node("AbsentUser", name=user, uid=uid)
                    userNode.__primarylabel__ = "AbsentUser"
                    userNode.__primarykey__ = "uid"
                
                try:
                    tx = graph.begin()
                    r1 = Relationship(groupNode, "CONTAIN USER", userNode)
                    node = tx.merge(groupNode) 
                    node = tx.merge(userNode) 
                    node = tx.merge(r1) 
                    graph.commit(tx)

                except Exception as e: 
                    if release:
                        print(e)
                        pass
                    else:
                        exc_type, exc_obj, exc_tb = sys.exc_info()
                        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                        print(exc_type, fname, exc_tb.tb_lineno)
                        print("Error:", e)
                        sys.exit(1)


##
## RoleBinding
## 
print("#### RoleBinding ####")

roleBindings = dyn_client.resources.get(api_version='rbac.authorization.k8s.io/v1', kind='RoleBinding')
roleBinding_list = roleBindings.get()

if "all" in collector or "rolebinding" in collector:
    nbObject = len(roleBinding_list.items)
    progress = 0.0
    for enum in roleBinding_list.items:
        progress=progress+1
        print("RoleBinding progress = {}%".format(progress/nbObject*100.0))

        # print(enum)
        name = enum.metadata.name
        uid = enum.metadata.uid
        namespace = enum.metadata.namespace
        description = enum.metadata.description

        rolebindingNode = Node("RoleBinding", name=name, namespace=namespace, uid=uid)
        rolebindingNode.__primarylabel__ = "RoleBinding"
        rolebindingNode.__primarykey__ = "uid"

        roleKind = enum.roleRef.kind
        roleName = enum.roleRef.name

        if roleKind == "ClusterRole":
            try:
                role = clusterroles.get(name=roleName)
                roleNode = Node("ClusterRole",name=role.metadata.name, uid=role.metadata.uid)
                roleNode.__primarylabel__ = "ClusterRole"
                roleNode.__primarykey__ = "uid"

            except: 
                uid = roleName
                roleNode = Node("AbsentClusterRole", name=roleName, uid=uid)
                roleNode.__primarylabel__ = "AbsentClusterRole"
                roleNode.__primarykey__ = "uid"

        elif roleKind == "Role":
            try:
                role = roles.get(name=roleName, namespace=enum.metadata.namespace)
                roleNode = Node("Role",name=role.metadata.name, namespace=role.metadata.namespace, uid=role.metadata.uid)
                roleNode.__primarylabel__ = "Role"
                roleNode.__primarykey__ = "uid"

            except: 
                uid = roleName + "_" + namespace
                roleNode = Node("AbsentRole",name=roleName, namespace=namespace, uid=uid)
                roleNode.__primarylabel__ = "AbsentRole"
                roleNode.__primarykey__ = "uid"

        if enum.subjects:
            for subject in enum.subjects:
                subjectKind = subject.kind
                subjectName = subject.name
                subjectNamespace = subject.namespace

                if not subjectNamespace:
                    subjectNamespace = namespace

                if subjectKind == "ServiceAccount": 
                    if subjectNamespace:
                        try:
                            project_list = projects.get(name=subjectNamespace)
                            projectNode = Node("Project",name=project_list.metadata.name, uid=project_list.metadata.uid)
                            projectNode.__primarylabel__ = "Project"
                            projectNode.__primarykey__ = "uid"

                        except: 
                            uid = subjectNamespace
                            projectNode = Node("AbsentProject", name=subjectNamespace, uid=uid)
                            projectNode.__primarylabel__ = "AbsentProject"
                            projectNode.__primarykey__ = "uid"

                        try:
                            serviceAccount = serviceAccounts.get(name=subjectName, namespace=subjectNamespace)
                            subjectNode = Node("ServiceAccount",name=serviceAccount.metadata.name, namespace=serviceAccount.metadata.namespace, uid=serviceAccount.metadata.uid)
                            subjectNode.__primarylabel__ = "ServiceAccount"
                            subjectNode.__primarykey__ = "uid"

                        except: 
                            uid = subjectName+"_"+subjectNamespace
                            subjectNode = Node("AbsentServiceAccount", name=subjectName, namespace=subjectNamespace, uid=uid)
                            subjectNode.__primarylabel__ = "AbsentServiceAccount"
                            subjectNode.__primarykey__ = "uid"
                            # print("!!!! serviceAccount related to Role: ", roleName ,", don't exist: ", subjectNamespace, ":", subjectName, sep='')

                        try:
                            tx = graph.begin()
                            r1 = Relationship(projectNode, "CONTAIN SA", subjectNode)
                            r2 = Relationship(subjectNode, "HAS ROLEBINDING", rolebindingNode)
                            if roleKind == "ClusterRole":
                                r3 = Relationship(rolebindingNode, "HAS CLUSTERROLE", roleNode)
                            elif roleKind == "Role":
                                r3 = Relationship(rolebindingNode, "HAS ROLE", roleNode)
                            node = tx.merge(projectNode) 
                            node = tx.merge(subjectNode) 
                            node = tx.merge(rolebindingNode) 
                            node = tx.merge(roleNode) 
                            node = tx.merge(r1) 
                            node = tx.merge(r2) 
                            node = tx.merge(r3) 
                            graph.commit(tx)

                        except Exception as e: 
                            if release:
                                print(e)
                                pass
                            else:
                                exc_type, exc_obj, exc_tb = sys.exc_info()
                                fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                                print(exc_type, fname, exc_tb.tb_lineno)
                                print("Error:", e)
                                sys.exit(1)

                elif subjectKind == "Group": 
                    if "system:serviceaccount:" in subjectName:
                        namespace = subjectName.split(":")
                        groupNamespace = namespace[2]

                        try:
                            project_list = projects.get(name=groupNamespace)
                            groupNode = Node("Project",name=project_list.metadata.name, uid=project_list.metadata.uid)
                            groupNode.__primarylabel__ = "Project"
                            groupNode.__primarykey__ = "uid"

                        except: 
                            uid = groupNamespace
                            groupNode = Node("AbsentProject", name=groupNamespace, uid=uid)
                            groupNode.__primarylabel__ = "AbsentProject"
                            groupNode.__primarykey__ = "uid"

                    elif "system:" in subjectName:
                        uid = subjectName
                        groupNode = Node("SystemGroup", name=subjectName, uid=uid)
                        groupNode.__primarylabel__ = "SystemGroup"
                        groupNode.__primarykey__ = "uid"

                    else:
                        try:
                            group_list = groups.get(name=subjectName)
                            groupNode = Node("Group", name=group_list.metadata.name, uid=group_list.metadata.uid)
                            groupNode.__primarylabel__ = "Group"
                            groupNode.__primarykey__ = "uid"

                        except: 
                            uid = subjectName
                            groupNode = Node("AbsentGroup", name=subjectName, uid=uid)
                            groupNode.__primarylabel__ = "AbsentGroup"
                            groupNode.__primarykey__ = "uid"

                    try:
                        tx = graph.begin()
                        r2 = Relationship(groupNode, "HAS ROLEBINDING", rolebindingNode)
                        if roleKind == "ClusterRole":
                            r3 = Relationship(rolebindingNode, "HAS CLUSTERROLE", roleNode)
                        elif roleKind == "Role":
                            r3 = Relationship(rolebindingNode, "HAS ROLE", roleNode)
                        node = tx.merge(groupNode) 
                        node = tx.merge(rolebindingNode) 
                        node = tx.merge(roleNode) 
                        node = tx.merge(r2) 
                        node = tx.merge(r3) 
                        graph.commit(tx)

                    except Exception as e: 
                        if release:
                            print(e)
                            pass
                        else:
                            exc_type, exc_obj, exc_tb = sys.exc_info()
                            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                            print(exc_type, fname, exc_tb.tb_lineno)
                            print("Error:", e)
                            sys.exit(1)

                elif subjectKind == "User": 

                    try:
                        user_list = users.get(name=subjectName)
                        userNode = Node("User", name=group_list.metadata.name, uid=group_list.metadata.uid)
                        userNode.__primarylabel__ = "User"
                        userNode.__primarykey__ = "uid"

                    except: 
                        uid = subjectName
                        userNode = Node("AbsentUser", name=subjectName, uid=uid)
                        userNode.__primarylabel__ = "AbsentUser"
                        userNode.__primarykey__ = "uid"

                    try:
                        tx = graph.begin()
                        r2 = Relationship(userNode, "HAS ROLEBINDING", rolebindingNode)
                        if roleKind == "ClusterRole":
                            r3 = Relationship(rolebindingNode, "HAS CLUSTERROLE", roleNode)
                        elif roleKind == "Role":
                            r3 = Relationship(rolebindingNode, "HAS ROLE", roleNode)
                        node = tx.merge(userNode) 
                        node = tx.merge(rolebindingNode) 
                        node = tx.merge(roleNode) 
                        node = tx.merge(r2) 
                        node = tx.merge(r3) 
                        graph.commit(tx)

                    except Exception as e: 
                        if release:
                            print(e)
                            pass
                        else:
                            exc_type, exc_obj, exc_tb = sys.exc_info()
                            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                            print(exc_type, fname, exc_tb.tb_lineno)
                            print("Error:", e)
                            sys.exit(1)

                else:
                    print("[-] RoleBinding subjectKind not handled", subjectKind)
                                

##
## ClusterRoleBinding
## 
print("#### ClusterRoleBinding ####")

clusterRoleBindings = dyn_client.resources.get(api_version='rbac.authorization.k8s.io/v1', kind='ClusterRoleBinding')
clusterRoleBinding_list = clusterRoleBindings.get()
 
if "all" in collector or "clusterrolebinding" in collector:
    nbObject = len(clusterRoleBinding_list.items)
    progress = 0.0
    for enum in clusterRoleBinding_list.items:
        progress=progress+1
        print("ClusterRoleBinding progress = {}%".format(progress/nbObject*100.0))

        # print(enum)
        name = enum.metadata.name
        uid = enum.metadata.uid
        namespace = enum.metadata.namespace
        description = enum.metadata.description

        clusterRolebindingNode = Node("ClusterRoleBinding", name=name, namespace=namespace, uid=uid)
        clusterRolebindingNode.__primarylabel__ = "RoleBinding"
        clusterRolebindingNode.__primarykey__ = "uid"

        roleKind = enum.roleRef.kind
        roleName = enum.roleRef.name

        if roleKind == "ClusterRole":
            try:
                role = clusterroles.get(name=roleName)
                roleNode = Node("ClusterRole",name=role.metadata.name, uid=role.metadata.uid)
                roleNode.__primarylabel__ = "ClusterRole"
                roleNode.__primarykey__ = "uid"

            except: 
                uid = roleName
                roleNode = Node("AbsentClusterRole",name=roleName, uid=uid)
                roleNode.__primarylabel__ = "AbsentClusterRole"
                roleNode.__primarykey__ = "uid"

        elif roleKind == "Role":
            try:
                role = roles.get(name=roleName, namespace=enum.metadata.namespace)
                roleNode = Node("Role",name=role.metadata.name, namespace=role.metadata.namespace, uid=role.metadata.uid)
                roleNode.__primarylabel__ = "Role"
                roleNode.__primarykey__ = "uid"

            except: 
                uid=roleName+"_"+namespace
                roleNode = Node("AbsentRole",name=roleName, namespace=namespace, uid=uid)
                roleNode.__primarylabel__ = "AbsentRole"
                roleNode.__primarykey__ = "uid"

        if enum.subjects:
            for subject in enum.subjects:
                subjectKind = subject.kind
                subjectName = subject.name
                subjectNamespace = subject.namespace

                if subjectKind == "ServiceAccount": 
                    if subjectNamespace:
                        try:
                            project_list = projects.get(name=subjectNamespace)
                            projectNode = Node("Project",name=project_list.metadata.name, uid=project_list.metadata.uid)
                            projectNode.__primarylabel__ = "Project"
                            projectNode.__primarykey__ = "uid"

                        except: 
                            uid = subjectNamespace
                            projectNode = Node("AbsentProject", name=subjectNamespace, uid=uid)
                            projectNode.__primarylabel__ = "AbsentProject"
                            projectNode.__primarykey__ = "uid"

                        try:
                            serviceAccount = serviceAccounts.get(name=subjectName, namespace=subjectNamespace)
                            subjectNode = Node("ServiceAccount",name=serviceAccount.metadata.name, namespace=serviceAccount.metadata.namespace, uid=serviceAccount.metadata.uid)
                            subjectNode.__primarylabel__ = "ServiceAccount"
                            subjectNode.__primarykey__ = "uid"

                        except: 
                            uid = subjectName+"_"+subjectNamespace
                            subjectNode = Node("AbsentServiceAccount", name=subjectName, namespace=subjectNamespace, uid=uid)
                            subjectNode.__primarylabel__ = "AbsentServiceAccount"
                            subjectNode.__primarykey__ = "uid"
                            # print("!!!! serviceAccount related to Role: ", roleName ,", don't exist: ", subjectNamespace, ":", subjectName, sep='')

                        try: 
                            tx = graph.begin()
                            r1 = Relationship(projectNode, "CONTAIN SA", subjectNode)
                            r2 = Relationship(subjectNode, "HAS CLUSTERROLEBINDING", clusterRolebindingNode)
                            if roleKind == "ClusterRole":
                                r3 = Relationship(clusterRolebindingNode, "HAS CLUSTERROLE", roleNode)
                            elif roleKind == "Role":
                                r3 = Relationship(clusterRolebindingNode, "HAS ROLE", roleNode)
                            node = tx.merge(projectNode) 
                            node = tx.merge(subjectNode) 
                            node = tx.merge(clusterRolebindingNode) 
                            node = tx.merge(roleNode) 
                            node = tx.merge(r1) 
                            node = tx.merge(r2) 
                            node = tx.merge(r3) 
                            graph.commit(tx)

                        except Exception as e: 
                            if release:
                                print(e)
                                pass
                            else:
                                exc_type, exc_obj, exc_tb = sys.exc_info()
                                fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                                print(exc_type, fname, exc_tb.tb_lineno)
                                print("Error:", e)
                                sys.exit(1)

                elif subjectKind == "Group": 
                    if "system:serviceaccount:" in subjectName:
                        namespace = subjectName.split(":")
                        groupNamespace = namespace[2]

                        try:
                            project_list = projects.get(name=groupNamespace)
                            groupNode = Node("Project",name=project_list.metadata.name, uid=project_list.metadata.uid)
                            groupNode.__primarylabel__ = "Project"
                            groupNode.__primarykey__ = "uid"

                        except: 
                            uid = groupNamespace
                            groupNode = Node("AbsentProject", name=groupNamespace, uid=uid)
                            groupNode.__primarylabel__ = "AbsentProject"
                            groupNode.__primarykey__ = "uid"

                    elif "system:" in subjectName:
                        uid = subjectName
                        groupNode = Node("SystemGroup", name=subjectName, uid=uid)
                        groupNode.__primarylabel__ = "SystemGroup"
                        groupNode.__primarykey__ = "uid"

                    else:
                        try:
                            group_list = groups.get(name=subjectName)
                            groupNode = Node("Group", name=group_list.metadata.name, uid=group_list.metadata.uid)
                            groupNode.__primarylabel__ = "Group"
                            groupNode.__primarykey__ = "uid"

                        except: 
                            uid = subjectName
                            groupNode = Node("AbsentGroup", name=subjectName, uid=uid)
                            groupNode.__primarylabel__ = "AbsentGroup"
                            groupNode.__primarykey__ = "uid"

                    try:
                        tx = graph.begin()
                        r2 = Relationship(groupNode, "HAS CLUSTERROLEBINDING", clusterRolebindingNode)
                        if roleKind == "ClusterRole":
                            r3 = Relationship(clusterRolebindingNode, "HAS CLUSTERROLE", roleNode)
                        elif roleKind == "Role":
                            r3 = Relationship(clusterRolebindingNode, "HAS ROLE", roleNode)
                        node = tx.merge(groupNode) 
                        node = tx.merge(clusterRolebindingNode) 
                        node = tx.merge(roleNode) 
                        node = tx.merge(r2) 
                        node = tx.merge(r3) 
                        graph.commit(tx)

                    except Exception as e: 
                        if release:
                            print(e)
                            pass
                        else:
                            exc_type, exc_obj, exc_tb = sys.exc_info()
                            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                            print(exc_type, fname, exc_tb.tb_lineno)
                            print("Error:", e)
                            sys.exit(1)

                elif subjectKind == "User": 

                    try:
                        user_list = users.get(name=subjectName)
                        userNode = Node("User", name=group_list.metadata.name, uid=group_list.metadata.uid)
                        userNode.__primarylabel__ = "User"
                        userNode.__primarykey__ = "uid"

                    except: 
                        uid = subjectName
                        userNode = Node("AbsentUser", name=subjectName, uid=uid)
                        userNode.__primarylabel__ = "AbsentUser"
                        userNode.__primarykey__ = "uid"

                    try:
                        tx = graph.begin()
                        r2 = Relationship(userNode, "HAS CLUSTERROLEBINDING", clusterRolebindingNode)
                        if roleKind == "ClusterRole":
                            r3 = Relationship(clusterRolebindingNode, "HAS CLUSTERROLE", roleNode)
                        elif roleKind == "Role":
                            r3 = Relationship(clusterRolebindingNode, "HAS ROLE", roleNode)
                        node = tx.merge(userNode) 
                        node = tx.merge(clusterRolebindingNode) 
                        node = tx.merge(roleNode) 
                        node = tx.merge(r2) 
                        node = tx.merge(r3) 
                        graph.commit(tx)

                    except Exception as e: 
                        if release:
                            print(e)
                            pass
                        else:
                            exc_type, exc_obj, exc_tb = sys.exc_info()
                            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                            print(exc_type, fname, exc_tb.tb_lineno)
                            print("Error:", e)
                            sys.exit(1)

                else:
                    print("[-] RoleBinding subjectKind not handled", subjectKind)


##
## Route
## 
print("#### Route ####")

if "all" in collector or "route" in collector:

    routes = dyn_client.resources.get(api_version='route.openshift.io/v1', kind='Route')
    route_list = routes.get()

    for enum in route_list.items:
        # print(enum.metadata)
        name = enum.metadata.name
        namespace = enum.metadata.namespace
        uid = enum.metadata.uid

        host = enum.spec.host
        path = enum.spec.path
        port= "any"
        if enum.spec.port:
            port = enum.spec.port.targetPort    

        try:
            project_list = projects.get(name=namespace)
            projectNode = Node("Project",name=project_list.metadata.name, uid=project_list.metadata.uid)
            projectNode.__primarylabel__ = "Project"
            projectNode.__primarykey__ = "uid"

        except: 
            uid = namespace
            projectNode = Node("AbsentProject",name=namespace, uid=uid)
            projectNode.__primarylabel__ = "AbsentProject"
            projectNode.__primarykey__ = "uid"

        routeNode = Node("Route",name=name, namespace=namespace, uid=uid, host=host, port=port, path=path)
        routeNode.__primarylabel__ = "Route"
        routeNode.__primarykey__ = "uid"

        try:
            tx = graph.begin()
            relationShip = Relationship(projectNode, "CONTAIN ROUTE", routeNode)
            node = tx.merge(projectNode) 
            node = tx.merge(routeNode) 
            node = tx.merge(relationShip) 
            graph.commit(tx)

        except Exception as e: 
            if release:
                print(e)
                pass
            else:
                exc_type, exc_obj, exc_tb = sys.exc_info()
                fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                print(exc_type, fname, exc_tb.tb_lineno)
                print("Error:", e)
                sys.exit(1)


##
## Pod
## 
print("#### Pod ####")

# if "all" in collector or "pod" in collector:
if "pod" in collector:
    pods = dyn_client.resources.get(api_version='v1', kind='Pod')
    pod_list = pods.get()

    for enum in pod_list.items:
        # print(enum.metadata)

        name = enum.metadata.name
        namespace = enum.metadata.namespace
        uid = enum.metadata.uid

        try:
            project_list = projects.get(name=namespace)
            projectNode = Node("Project",name=project_list.metadata.name, uid=project_list.metadata.uid)
            projectNode.__primarylabel__ = "Project"
            projectNode.__primarykey__ = "uid"

        except: 
            projectNode = Node("AbsentProject",name=namespace)
            projectNode.__primarylabel__ = "AbsentProject"
            projectNode.__primarykey__ = "name"

        podNode = Node("Pod",name=name, namespace=namespace, uid=uid)
        podNode.__primarylabel__ = "Pod"
        podNode.__primarykey__ = "uid"

        try:
            tx = graph.begin()
            relationShip = Relationship(projectNode, "CONTAIN POD", podNode)
            node = tx.merge(projectNode) 
            node = tx.merge(podNode) 
            node = tx.merge(relationShip) 
            graph.commit(tx)

        except Exception as e: 
            if release:
                print(e)
                pass
            else:
                exc_type, exc_obj, exc_tb = sys.exc_info()
                fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                print(exc_type, fname, exc_tb.tb_lineno)
                print("Error:", e)
                sys.exit(1)

##
## ConfigMap
## 
print("#### ConfigMap ####")

# if "all" in collector or "configmap" in collector:
if "configmap" in collector:
    configmaps = dyn_client.resources.get(api_version='v1', kind='ConfigMap')
    configmap_list = configmaps.get()

    for enum in configmap_list.items:
        # print(enum.metadata)

        name = enum.metadata.name
        namespace = enum.metadata.namespace
        uid = enum.metadata.uid

        try:
            project_list = projects.get(name=namespace)
            projectNode = Node("Project",name=project_list.metadata.name, uid=project_list.metadata.uid)
            projectNode.__primarylabel__ = "Project"
            projectNode.__primarykey__ = "uid"

        except: 
            projectNode = Node("AbsentProject",name=namespace)
            projectNode.__primarylabel__ = "AbsentProject"
            projectNode.__primarykey__ = "name"

        configmapNode = Node("ConfigMap",name=name, namespace=namespace, uid=uid)
        configmapNode.__primarylabel__ = "ConfigMap"
        configmapNode.__primarykey__ = "uid"

        try:
            tx = graph.begin()
            relationShip = Relationship(projectNode, "CONTAIN CONFIGMAP", configmapNode)
            node = tx.merge(projectNode) 
            node = tx.merge(configmapNode) 
            node = tx.merge(relationShip) 
            graph.commit(tx)

        except Exception as e: 
            if release:
                print(e)
                pass
            else:
                exc_type, exc_obj, exc_tb = sys.exc_info()
                fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                print(exc_type, fname, exc_tb.tb_lineno)
                print("Error:", e)
                sys.exit(1)


