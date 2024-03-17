# OpenShift Enumeration

This repository contain 2 scripts, AbsentEnum.py is use to detect absent SA that could represent a vulnerability and GenClusterGraph.py that is used to enumerate more largely the cluster.  

For AbsentEnum.py their is no need to install the neo4j database and it can be used with the following dependency:  
pip install openshift  

```bash
python3 AbsentEnum.py -a "https://api.cluster.net:6443" -t $(cat quota.token)
```

Output are the following:  

```
[o] serviceAccount related to ClusterRole: uniping-operator, don't exist: uniping:uniping-operator     			-> the uniping-operator SA is missing 
[+] serviceAccount and project related to ClusterRole: uniping-operator, don't exist: uniping:uniping-operator 	-> the uniping-operator SA and the uniping project are missing 
```

## What it is

The script is mean to create relational database from openshift cluster information read with a quota-admin account.  
It extract data as nodes and relation as relationship for commun information like projects, service accounts, scc and others.  
The query system is then use to spot inconsistency in the database.  

## How to use

### Install

The script need to communicate with the neo4j database and the openshift cluster in python:  

pip install py2neo  
pip install openshift  

To install the neo4j database we recomment to install neo4j desktop, which contain the database and bloom for visualisation:  

https://neo4j.com/download/  

### Setup

Then script can be launch with the following command:  

```bash
python3 GenClusterGraph.py -a "https://api.cluster.net:6443" -t $(cat quota.token) -c all
```

## Exemples of Queries

```
MATCH (n:AbsentServiceAccount {name:"servicenow-sa"}) RETURN n LIMIT 25  

MATCH p=(n1:Project) WHERE NOT (n1.name =~ ('openshift.*') OR n1.name =~ ('test'))  RETURN p LIMIT 25  

MATCH p=(n:AbsentServiceAccount {name:"servicenow-sa"})-[r:`HAS CLUSTER ROLE`]->() RETURN p LIMIT 25  

MATCH p=(n1:AbsentProject)-[r1:`CONTAIN SA`]->(n2:AbsentServiceAccount)-[r2:`HAS CLUSTER ROLE`]->() RETURN p LIMIT 25  

MATCH p=(n1:AbsentProject)-[r1:`CONTAIN SA`]->(n2:AbsentServiceAccount)-[]->()-[r2:`get`]->(n4:Resource) WHERE (n4.name =~ ('secrets')) RETURN p LIMIT 25  

MATCH p=(n1:Project)-[r1:`CONTAIN SA`]->(n2:ServiceAccount)-[]->()-[r2:`get`]->(n4:Resource) WHERE (n4.name =~ ('secrets')) RETURN p LIMIT 25  

MATCH p=(n1:AbsentProject)-[r1:`CONTAIN SA`]->(n2:AbsentServiceAccount)-[r2:`CAN USE SCC`]->() RETURN p LIMIT 25  

MATCH p=(n2:AbsentServiceAccount)-[r2:`CAN USE SCC`]->() RETURN p LIMIT 25  

MATCH p=()-[r2:`HAS CLUSTER ROLE`]->()-[r1:`create`]->() RETURN p LIMIT 25  

MATCH p=(n1:Role)-[r1:`create`]->() RETURN p LIMIT 25  

MATCH p=(n2:ServiceAccount)-[]->(n1:Role)-[]->() RETURN p LIMIT 100  

MATCH p=(n2:AbsentServiceAccount)-[]->(n1:Role)-[r1:`create`]->() RETURN p LIMIT 100  

MATCH p=(n1)-[r2:`CAN USE SCC`]->(n2) WHERE NOT (n2.name =~ ('acs-splunk'))  RETURN p LIMIT 25  

MATCH p=(n1)-[r2:`CAN USE SCC`]->(n2) WHERE NOT (n2.name =~ ('acs-splunk.*'))  RETURN p LIMIT 25  

MATCH p=(n4:Resource) WHERE (n4.name =~ ('secrets')) RETURN p LIMIT 25  

MATCH p=(n1:Project)-[]->(n2:ServiceAccount)-[]->(n3:Role)-[r1:`*`]->(n4:Resource) WHERE NOT (n1.name =~ ('openshift.*') OR n1.name =~ ('test'))  RETURN p LIMIT 25  

MATCH p=(n4:Resource) WHERE (n4.name =~ ('.*bypass.*')) RETURN p LIMIT 25  

MATCH p=(n1:Project)-[]->(n2:ServiceAccount)-[]->(n3:Role)-[]->(n4:Resource) WHERE NOT (n1.name =~ ('openshift.*'))  RETURN p LIMIT 1000

MATCH p=(n1:Project)-[]->(n2:ServiceAccount)-[]->(n3:Role)-[]->(n4:Resource) RETURN p LIMIT 1000

MATCH p=(n1:Project)-[r1:`CONTAIN SA`]->(n2:ServiceAccount)-[]->()-[r2:`get`]->(n4:Resource) WHERE (n4.name =~ ('secrets')) AND NOT (n1.name =~ ('openshift.*')) RETURN p LIMIT 200  

MATCH p=(n1:Project)-[r1:`CONTAIN SA`]->(n2:ServiceAccount)-[]->()-[r2:`create`]->(n4:Resource) WHERE (n4.name =~ ('namespaces')) AND NOT (n1.name =~ ('openshift.*')) RETURN p LIMIT 200  

```

### SA not in openshift* project that can use SCC

```
MATCH p=(n1:Project)-[]->(n2:ServiceAccount)-[r1:`CAN USE SCC`]->() WHERE NOT (n1.name =~ ('openshift.*'))  RETURN p LIMIT 100
```

### SA not in openshift* project that has cluster role that can read secrets

```
MATCH p=(n1:Project)-[r1:`CONTAIN SA`]->(n2:ServiceAccount)-[r2:`HAS CLUSTER ROLE`]->()-[r3:`get`]->(n4:Resource) WHERE (n4.name =~ ('secrets')) AND NOT (n1.name =~ ('openshift.*')) RETURN p LIMIT 200  
```

## Vulnerabilities

### Absent SA that can use SCC

```
MATCH p=(n1:AbsentProject)-[r1:`CONTAIN SA`]->(n2:AbsentServiceAccount)-[r2:`CAN USE SCC`]->() RETURN p LIMIT 25  
```

### Absent SA that has cluster role

```
MATCH p=(n1:AbsentProject)-[r1:`CONTAIN SA`]->(n2:AbsentServiceAccount)-[r2:`HAS CLUSTER ROLE`]->() RETURN p LIMIT 25  
```