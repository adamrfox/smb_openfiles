#!/usr/local/bin/python

import papi
import isi_sdk
from isi_sdk.rest import ApiException
from pprint import pprint
import urllib3
urllib3.disable_warnings()
import getpass
import json
import sys
import getopt
import socket
import netaddr
import re
from unidecode import unidecode

def get_openfiles (node, user, password, limit, resume):
  uri = "https://" + node + ":8080"
  api_client = isi_sdk.ApiClient (uri)
  api_inst = isi_sdk.ProtocolsApi(api_client)
  try:
    if resume is None:
      resp = api_inst.get_smb_openfiles (limit=limit)
    else:
      resp = api_inst.get_smb_openfiles (resume=resume)
  except ApiException as e:
      print "Exception in get_smb_openfiles: %s\n" % e
      exit (1)
  return (resp)

def dprint (message):
  if DEBUG:
    print "DEBUG: " + message + "\n"

def api_check (host, user, password):
  global cluster
  host_uri = "https://" + host + ":8080"
  api_client = isi_sdk.ApiClient (host_uri)
  api_inst = isi_sdk.ClusterApi(api_client)
  try:
    ip = socket.gethostbyname (host)
  except:
    return (False)
  try:
    api_response = api_inst.get_cluster_config()
  except ApiException as e:
    print "Exception when calling ClusterApi->get_cluster_config: %s\n" % e
    return (False)
  cluster =  api_response.name
  return (True)

def get_pool_from_ip (data, addr):
  pool = ""
  addr_o = netaddr.IPAddress (addr)
  for i , inf in enumerate (data['pools']):
    for j, rng in enumerate (data['pools'][i]['ranges']):
      ip_range = list (netaddr.iter_iprange(data['pools'][i]['ranges'][j]['low'], data['pools'][i]['ranges'][j]['high']))
      if (addr_o in ip_range):
        pool = data['pools'][i]['id']
        return (pool)
  return (pool)

def get_addr_from_int (int_d, pool_d, pool):
  for x, p in enumerate (pool_d['pools']):
    if pool_d['pools'][x]['id'] == pool:
      for y, r in enumerate (pool_d['pools'][x]['ranges']):
        ip_range = list (netaddr.iter_iprange(pool_d['pools'][x]['ranges'][y]['low'],pool_d['pools'][x]['ranges'][y]['high']))
        for z, s in enumerate (int_d['ip_addrs']):
          ip_a = netaddr.IPAddress(int_d['ip_addrs'][z])
          if (ip_a in ip_range):
            return (int_d['ip_addrs'][z])


def get_addr_list_from_pool (ifs_d, pool_d,pool):
  found_addr = ""
  pf = pool.split ('.')
  for i, inf in enumerate (ifs_d['interfaces']):
    for j, own in enumerate (ifs_d['interfaces'][i]['owners']):
      if ifs_d['interfaces'][i]['owners'][j]['groupnet'] == pf[0] and ifs_d['interfaces'][i]['owners'][j]['subnet'] == pf[1] and ifs_d['interfaces'][i]['owners'][j]['pool'] == pf[2]:
        found_addr = get_addr_from_int(ifs_d['interfaces'][i], pool_d, pool)
        lnn = str(ifs_d['interfaces'][i]['lnn'])
        addr_list[lnn] = found_addr
#        addr_list.append (found_addr)
        break
  return (addr_list)

#
# Note: Bug in API for isi networks.  Keeping this PAPI
#
def get_addr_list (host, user, password):
  path = "/platform/3/network/interfaces?sort=lnn&dir=ASC"
  (status, reason, resp) = papi.call (host, '8080', 'GET', path, 'any', '', 'application/json', user, password)
  if status != 200:
    print "Bad Status: /network/interfaces: " + str(status)
    exit (status)
  int_data = json.loads (resp)
  path = "/platform/3/network/pools"
  (status, reason, resp) = papi.call (host, '8080', 'GET', path, 'any', '', 'application/json', user, password)
  if status != 200:
    print "Bad Status: /network/pools: " + str(status)
    exit (status)
  pool_data = json.loads (resp)
  pool = get_pool_from_ip (pool_data, host)
  return (get_addr_list_from_pool (int_data, pool_data, pool))


def usage ():
  sys.stderr.write ("Usage: smb_openfiles[.py]\n")
  sys.stderr.write ("	List Files (default mode):\n")
  sys.stderr.write ("		[{-C | --cluster}] : Specify a cluster from the config file\n")
  sys.stderr.write ("		[{-f | --file}] : Specify an alternative config file\n")
  sys.stderr.write ("	Close File Mode:\n")
  sys.stderr.write ("		[{-c | --close}] : Close file(s) Selects Close File Mode\n")
  sys.stderr.write ("		[{-n | --node]} : Specifies a node where the file is open\n")
  sys.stderr.write ("		[{-i | id}] : Specify a comma-separated list of IDs\n")
  sys.stderr.write ("	[-h | --help] : display usage syntax\n\n")
  exit (0)



cluster = ''
cluster_list = {}
user = ""
password = ""
conf_file = "nodes.conf"
MODE = "view"
node = ""
id_list = []
user_name = ""
addr_list = {}
node_num_s = ""
file_flag = False
cluster_flag = False
has_v3_api = False
DEBUG = 0
ALL = 1
limit = 50
resume = None
match = None

optlist, args = getopt.getopt (sys.argv[1:], 'DC:f:cn:i:hl:m:', ["cluster=", "file=", "close", "node=", "id=", "help", "limit=", "match="])
for opt, a in optlist:
  if opt == '-D':
    DEBUG = 1
  if opt in ('-C', "--cluster"):
    ALL = 0
    cluster_flag = True
    cluster = a
  if opt in ('-f', "--file"):
    file_flag = True
    conf_file = a
  if opt in ('-c', "--close"):
    MODE = "close"
  if opt in ('-n', "--node"):
    node_num_s = a
  if opt in ('-i', "--id"):
    ids = a.split(',')
    for i in ids:
      id_list.append(i)
  if opt in ('-h' , "--help"):
    usage()
  if opt in ('-l', "--limit"):
    limit = a
  if opt in ('-m', "--match"):
    match = a

user = raw_input ("User: ")
password = getpass.getpass ("Password: ")
isi_sdk.configuration.username = user
isi_sdk.configuration.password = password
isi_sdk.configuration.verify_ssl = False

if cluster_flag == False and file_flag == False:
  if MODE == "view":
    x = len (sys.argv)-1
    host = sys.argv[x]
    has_v3_api = api_check (host, user, password)
  else:
    nnf = node_num_s.split ('-')
    node_name = nnf[0]
    node_num = nnf[1]
    check1 = api_check (node_num_s, user, password)
    check2 = api_check (node_name, user, password)
    if check1 == True:
      has_v3_api = True
      host = node_num_s
    elif check2 == True:
      has_v3_api = True
      host = node_name
    else:
      has_v3_api = False
if has_v3_api ==  False:
  for node in open (conf_file):
    node_s = node.rstrip ('\r\n')
    nl = node_s.split (':')
    if ALL == 0 and nl[0] != cluster:
      continue
    cluster_list[nl[1]] = nl[0]
    addr_list[nl[1]] = nl[2]
  if (len(addr_list) == 0):
    print "No Clusters Found."
    exit (0)
else:
  addr_list = get_addr_list (host, user, password)
  for i in addr_list.keys():
    if addr_list[i] != None:
      cluster_list[i] = cluster
if MODE == "view":
  for i in sorted(cluster_list.keys()):
    done = False
    first_run = True
    node_name = cluster_list[i] + "-" + str(i) + ":"
    print "--------------------------------------"
    while done == False:
      ofiles = get_openfiles (addr_list[i], user, password, limit, resume)
      if first_run is True:
        if ofiles.total == 0:
          print node_name, "No Open Files"
        else:
          print node_name
          print "ID: File:                                    User:            #Locks:"
        print "--------------------------------------"
        first_run = False
      resume = ofiles.resume
      if resume is None:
        done = True
      for file_inst in ofiles.openfiles:
        if match is not None:
          name_match = re.search (match, file_inst.file)
          user_match = re.search (match, file_inst.user)
          if name_match is None and user_match is None:
            continue
        try:
          print "{0:3d} {1:40s} {2:15s} {3:2d}".format(file_inst.id,file_inst.file,file_inst.user,file_inst.locks)  
        except UnicodeEncodeError:
          file_name = unidecode (file_inst.file)
          print "{0:3d} {1:40s} {2:15s} {3:2d}".format(file_inst.id,file_name,file_inst.user,file_inst.locks)  
    print ""
else:
  if node_num_s == "" or len(id_list) == 0:
    sys.stderr.write ("To close a file the node and ID must be specificed.\n")
    usage()
    exit (2)
  nnf = node_num_s.split ('-')
  node_name = nnf[0]
  node_num = nnf[1]
  for id in id_list:
    path = "/platform/1/protocols/smb/openfiles/" + id
    dprint (path)
    dprint (addr_list[node_num])
    (status, resp, reason) = papi.call (addr_list[node_num], '8080', 'DELETE', path, 'any', '', 'application/json', user, password)
    if status != 204:
      err_string = "Bad Status: " + `status` + "\n"
      sys.stderr.write (err_string)
      err = json.loads (reason)
      sys.stderr.write (err['errors'][0]['message'])
      sys.stderr.write ("\n")
      exit (status)
    print "ID " + id + " Closed."

