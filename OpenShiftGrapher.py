import argparse
from argparse import RawTextHelpFormatter
import sys

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
parser.add_argument('-c', '--collector', nargs="+", default=[], help='list of collectors. Possible values: all, project, scc, sa, role, clusterrole, route, pod ')
parser.add_argument('-u', '--userNeo4j', default="neo4j", help='neo4j database user.')
parser.add_argument('-p', '--passwordNeo4j', default="rootroot", help='neo4j database password.')

args = parser.parse_args()

hostApi = args.apiUrl
api_key = args.token
resetDB = args.resetDB
userNeo4j = args.userNeo4j
passwordNeo4j = args.passwordNeo4j
collector = args.collector


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
        tx = graph.begin()
        a = Node("Project", name=enum.metadata.name, uid=enum.metadata.uid)
        a.__primarylabel__ = "Project"
        a.__primarykey__ = "uid"
        node = tx.merge(a) 
        graph.commit(tx)


##
## Service account
##
print("#### Service Account ####")

serviceAccounts = dyn_client.resources.get(api_version='v1', kind='ServiceAccount')
serviceAccount_list = serviceAccounts.get()
 
if "all" in collector or "sa" in collector:
    for enum in serviceAccount_list.items:
        # print(enum.metadata)
        tx = graph.begin()
        a = Node("ServiceAccount", name=enum.metadata.name, namespace=enum.metadata.namespace, uid=enum.metadata.uid)
        a.__primarylabel__ = "ServiceAccount"
        a.__primarykey__ = "uid"

        project_list = projects.get(name=enum.metadata.namespace)

        b = Node("Project", name=enum.metadata.namespace, uid=project_list.metadata.uid)
        b.__primarylabel__ = "Project"
        b.__primarykey__ = "uid"

        r2 = Relationship(b, "CONTAIN SA", a)

        node = tx.merge(a) 
        node = tx.merge(b) 
        node = tx.merge(r2) 
        graph.commit(tx)


##
## SSC
##
print("#### SSC ####")

SSCs = dyn_client.resources.get(api_version='security.openshift.io/v1', kind='SecurityContextConstraints')
SSC_list = SSCs.get()
 
if "all" in collector or "scc" in collector:
    for enum in SSC_list.items:
        # print(enum.metadata)
        tx = graph.begin()
        a = Node("SCC",name=enum.metadata.name, uid=enum.metadata.uid)
        a.__primarylabel__ = "SCC"
        a.__primarykey__ = "uid"
        node = tx.merge(a) 
        graph.commit(tx)


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
                    subjectNode = Node("ServiceAccount",name=serviceAccount.metadata.name, namespace=serviceAccount.metadata.namespace, uid=serviceAccount.metadata.uid)
                    subjectNode.__primarylabel__ = "ServiceAccount"
                    subjectNode.__primarykey__ = "uid"
                except: 
                    subjectNode = Node("AbsentServiceAccount", name=subjectName, namespace=subjectNamespace)
                    subjectNode.__primarylabel__ = "AbsentServiceAccount"
                    subjectNode.__primarykey__ = "name"  
                    # print("!!!! serviceAccount related to SSC: ", enum.metadata.name ,", don't exist: ", subjectNamespace, ":", subjectName, sep='')    

                try:
                    project_list = projects.get(name=subjectNamespace)
                    projectNode = Node("Project",name=project_list.metadata.name, uid=project_list.metadata.uid)
                    projectNode.__primarylabel__ = "Project"
                    projectNode.__primarykey__ = "uid"

                except: 
                    projectNode = Node("AbsentProject",name=subjectNamespace)
                    projectNode.__primarylabel__ = "AbsentProject"
                    projectNode.__primarykey__ = "name"      

                tx = graph.begin()
                a = Node("SCC",name=enum.metadata.name, uid=enum.metadata.uid)
                a.__primarylabel__ = "SCC"
                a.__primarykey__ = "uid"
                r1 = Relationship(projectNode, "CONTAIN SA", subjectNode)
                r2 = Relationship(subjectNode, "CAN USE SCC", a)
                node = tx.merge(projectNode) 
                node = tx.merge(subjectNode) 
                node = tx.merge(a) 
                node = tx.merge(r2) 
                graph.commit(tx)


##
## Role
## 
print("#### Role ####")

roles = dyn_client.resources.get(api_version='rbac.authorization.k8s.io/v1', kind='Role')
role_list = roles.get()
 
if "all" in collector or "role" in collector:
    for enum in role_list.items:
        # print(enum.metadata)
        tx = graph.begin()
        a = Node("Role",name=enum.metadata.name, namespace=enum.metadata.namespace, uid=enum.metadata.uid)
        a.__primarylabel__ = "Role"
        a.__primarykey__ = "uid"
        node = tx.merge(a) 
        graph.commit(tx)


##
## ClusterRole
## 
print("#### ClusterRole ####")

clusterroles = dyn_client.resources.get(api_version='rbac.authorization.k8s.io/v1', kind='ClusterRole')
clusterrole_list = clusterroles.get()
 
if "all" in collector or "clusterrole" in collector:
    for enum in clusterrole_list.items:
        # print(enum.metadata)
        tx = graph.begin()
        a = Node("ClusterRole",name=enum.metadata.name, uid=enum.metadata.uid)
        a.__primarylabel__ = "ClusterRole"
        a.__primarykey__ = "uid"
        node = tx.merge(a) 
        graph.commit(tx)


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

        if roleKind == "ClusterRole":
            try:
                role = clusterroles.get(name=roleName)
            except: 
                # print(enum)
                # exit()
                continue

            roleNode = Node("ClusterRole",name=role.metadata.name, uid=role.metadata.uid)
            roleNode.__primarylabel__ = "ClusterRole"
            roleNode.__primarykey__ = "uid"

        elif roleKind == "Role":
            try:
                role = roles.get(name=roleName, namespace=enum.metadata.namespace)
            except: 
                # print(enum)
                # exit()
                continue

            roleNode = Node("Role",name=role.metadata.name, namespace=role.metadata.namespace, uid=role.metadata.uid)
            roleNode.__primarylabel__ = "Role"
            roleNode.__primarykey__ = "uid"

        if role.rules:
            for rule in role.rules:
                if rule.apiGroups:
                    for apiGroup in rule.apiGroups:
                        for resource in rule.resources:
                            for verb in rule.verbs:

                                if apiGroup == "":
                                    resourceName = resource
                                else:
                                    resourceName = apiGroup
                                    resourceName = ":"
                                    resourceName = resource

                                ressourceNode = Node("Resource", name=resourceName)
                                ressourceNode.__primarylabel__ = "Resource"
                                ressourceNode.__primarykey__ = "name"

                                tx = graph.begin()
                                if verb == "impersonate":
                                    r1 = Relationship(roleNode, "impers", ressourceNode)  
                                else:
                                    r1 = Relationship(roleNode, verb, ressourceNode)
                                node = tx.merge(roleNode) 
                                node = tx.merge(ressourceNode) 
                                node = tx.merge(r1) 
                                graph.commit(tx)

                if rule.nonResourceURLs: 
                    for nonResourceURL in rule.nonResourceURLs: 
                        for verb in rule.verbs:

                            ressourceNode = Node("ResourceNoUrl", name=nonResourceURL)
                            ressourceNode.__primarylabel__ = "ResourceNoUrl"
                            ressourceNode.__primarykey__ = "name"

                            tx = graph.begin()
                            r1 = Relationship(roleNode, verb, ressourceNode)
                            node = tx.merge(roleNode) 
                            node = tx.merge(ressourceNode) 
                            node = tx.merge(r1) 
                            graph.commit(tx)

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
                            projectNode = Node("AbsentProject",name=subjectNamespace)
                            projectNode.__primarylabel__ = "AbsentProject"
                            projectNode.__primarykey__ = "name"

                        try:
                            serviceAccount = serviceAccounts.get(name=subjectName, namespace=subjectNamespace)
                            subjectNode = Node("ServiceAccount",name=serviceAccount.metadata.name, namespace=serviceAccount.metadata.namespace, uid=serviceAccount.metadata.uid)
                            subjectNode.__primarylabel__ = "ServiceAccount"
                            subjectNode.__primarykey__ = "uid"

                        except: 
                            subjectNode = Node("AbsentServiceAccount", name=subjectName, namespace=subjectNamespace)
                            subjectNode.__primarylabel__ = "AbsentServiceAccount"
                            subjectNode.__primarykey__ = "name"
                            # print("!!!! serviceAccount related to Role: ", roleName ,", don't exist: ", subjectNamespace, ":", subjectName, sep='')

                        tx = graph.begin()
                        r1 = Relationship(projectNode, "CONTAIN SA", subjectNode)
                        r2 = Relationship(subjectNode, "HAS ROLE", roleNode, description=description)
                        node = tx.merge(roleNode) 
                        node = tx.merge(subjectNode) 
                        node = tx.merge(r1) 
                        node = tx.merge(r2) 
                        graph.commit(tx)
                                

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

        if roleKind == "ClusterRole":
            try:
                role = clusterroles.get(name=roleName)
            except: 
                # print(enum)
                # exit()
                continue

            roleNode = Node("ClusterRole",name=role.metadata.name, uid=role.metadata.uid)
            roleNode.__primarylabel__ = "ClusterRole"
            roleNode.__primarykey__ = "uid"

        elif roleKind == "Role":
            try:
                role = roles.get(name=roleName, namespace=enum.metadata.namespace)
            except: 
                # print(enum)
                # exit()
                continue

            roleNode = Node("Role",name=role.metadata.name, namespace=role.metadata.namespace, uid=role.metadata.uid)
            roleNode.__primarylabel__ = "Role"
            roleNode.__primarykey__ = "uid"

        if role.rules:
            for rule in role.rules:
                if rule.apiGroups:
                    for apiGroup in rule.apiGroups:
                        for resource in rule.resources:
                            for verb in rule.verbs:

                                if apiGroup == "":
                                    resourceName = resource
                                else:
                                    resourceName = apiGroup
                                    resourceName = ":"
                                    resourceName = resource

                                ressourceNode = Node("Resource", name=resourceName)
                                ressourceNode.__primarylabel__ = "Resource"
                                ressourceNode.__primarykey__ = "name"
                                
                                tx = graph.begin()
                                if verb == "impersonate":
                                    r1 = Relationship(roleNode, "impers", ressourceNode)  
                                else:
                                    r1 = Relationship(roleNode, verb, ressourceNode)
                                node = tx.merge(roleNode) 
                                node = tx.merge(ressourceNode) 
                                node = tx.merge(r1) 
                                graph.commit(tx)

                if rule.nonResourceURLs: 
                    for nonResourceURL in rule.nonResourceURLs: 
                        for verb in rule.verbs:

                            ressourceNode = Node("ResourceNoUrl", name=nonResourceURL)
                            ressourceNode.__primarylabel__ = "ResourceNoUrl"
                            ressourceNode.__primarykey__ = "name"

                            tx = graph.begin()
                            r1 = Relationship(roleNode, verb, ressourceNode)
                            node = tx.merge(roleNode) 
                            node = tx.merge(ressourceNode) 
                            node = tx.merge(r1) 
                            graph.commit(tx)

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
                            projectNode = Node("AbsentProject",name=subjectNamespace)
                            projectNode.__primarylabel__ = "AbsentProject"
                            projectNode.__primarykey__ = "name"

                        try:
                            serviceAccount = serviceAccounts.get(name=subjectName, namespace=subjectNamespace)
                            subjectNode = Node("ServiceAccount",name=serviceAccount.metadata.name, namespace=serviceAccount.metadata.namespace, uid=serviceAccount.metadata.uid)
                            subjectNode.__primarylabel__ = "ServiceAccount"
                            subjectNode.__primarykey__ = "uid"

                        except: 
                            subjectNode = Node("AbsentServiceAccount", name=subjectName, namespace=subjectNamespace)
                            subjectNode.__primarylabel__ = "AbsentServiceAccount"
                            subjectNode.__primarykey__ = "name"
                            # print("!!!! serviceAccount related to ClusterRole: ", roleName ,", don't exist: ", subjectNamespace, ":", subjectName, sep='')

                        tx = graph.begin()
                        r1 = Relationship(projectNode, "CONTAIN SA", subjectNode)
                        r2 = Relationship(subjectNode, "HAS CLUSTER ROLE", roleNode, description=description)
                        node = tx.merge(roleNode) 
                        node = tx.merge(subjectNode) 
                        node = tx.merge(r1) 
                        node = tx.merge(r2) 
                        graph.commit(tx)


##
## Route
## 
print("#### Route ####")

routes = dyn_client.resources.get(api_version='route.openshift.io/v1', kind='Route')
route_list = routes.get()

if "all" in collector or "route" in collector:
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
            projectNode = Node("AbsentProject",name=namespace)
            projectNode.__primarylabel__ = "AbsentProject"
            projectNode.__primarykey__ = "name"

        routeNode = Node("Route",name=name, namespace=namespace, uid=uid, host=host, port=port, path=path)
        routeNode.__primarylabel__ = "Route"
        routeNode.__primarykey__ = "uid"

        tx = graph.begin()
        relationShip = Relationship(projectNode, "CONTAIN ROUTE", routeNode)
        node = tx.merge(projectNode) 
        node = tx.merge(routeNode) 
        node = tx.merge(relationShip) 
        graph.commit(tx)


##
## DEV
##


##
## Enum all
##
# print("#### All ####")

# allRessources = dyn_client.resources.get()
# allRessource_list = allRessources.get()
# for enum in allRessource_list.items:
#     print(enum)



##
## Pod
## 
# print("#### Pod ####")

# pods = dyn_client.resources.get(api_version='v1', kind='Pod')
# pod_list = pods.get()

# if "all" in collector or "pod" in collector:
#     for enum in pod_list.items:
#         print(enum.metadata)

        # name = enum.metadata.name
        # namespace = enum.metadata.namespace
        # uid = enum.metadata.uid

        # host = enum.spec.host
        # path = enum.spec.path
        # port= "any"
        # if enum.spec.port:
        #     port = enum.spec.port.targetPort    

        # try:
        #     project_list = projects.get(name=namespace)
        #     projectNode = Node("Project",name=project_list.metadata.name, uid=project_list.metadata.uid)
        #     projectNode.__primarylabel__ = "Project"
        #     projectNode.__primarykey__ = "uid"

        # except: 
        #     projectNode = Node("AbsentProject",name=namespace)
        #     projectNode.__primarylabel__ = "AbsentProject"
        #     projectNode.__primarykey__ = "name"

        # routeNode = Node("Route",name=name, namespace=namespace, uid=uid, host=host, port=port, path=path)
        # routeNode.__primarylabel__ = "Route"
        # routeNode.__primarykey__ = "uid"

        # tx = graph.begin()
        # relationShip = Relationship(projectNode, "CONTAIN ROUTE", routeNode)
        # node = tx.merge(projectNode) 
        # node = tx.merge(routeNode) 
        # node = tx.merge(relationShip) 
        # graph.commit(tx)


##
## Test
## 
# print("#### Test ####")

# role = clusterroles.get(name="admin")


# if role.rules:
#     for rule in role.rules:
#         if rule.apiGroups:
#             for apiGroup in rule.apiGroups:
#                 for resource in rule.resources:
#                     for verb in rule.verbs:
#                         if apiGroup == "":
#                             print("void", resource, verb)


# print("#### Secret ####")

# pods = dyn_client.resources.get(api_version='v1', kind='Secret')
# pod_list = pods.get()

# for enum in pod_list.items:
#     print(enum.metadata)
