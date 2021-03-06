#!/usr/bin/python
import os
import json
import random
import re
import pyprind
import shutil
import argparse
import textwrap
import xml.etree.ElementTree as ET
from xml.etree.ElementTree import Element
from xml.etree.ElementTree import tostring
from pycocotools.coco import COCO
from xml.dom import minidom

filename_pattern = re.compile(r"(\S+)\.(xml|json)")
gen_pattern = re.compile(r"(\S*?)(\d+)\.(xml|json)")
number_pattern = re.compile(r"(\S*?)(\d+)")


def get(root, name):
    vars = root.findall(name)
    return vars

def get_value(root, name):
    vars = root.findall(name)
    if len(vars) == 0:
        raise NotImplementedError('Can not find %s in %s.'%(name, root.tag))
    if len(vars) != 1:
        raise NotImplementedError('The size of %s is supposed to be 1, but is %d.'%(name,len(vars)))
    re = vars[0].text
    try:
        return int(float(re))
    except Exception:
        return re

def get_class_number(name):
    number = 0
    if name == "work_uniformm":
        name = "work_uniform"
    if name == "othe_hat":
        name = "other_hat"
    with open(os.path.join("meta.json"), "r") as f:
        coco = json.load(f)
    for one in coco["categories"]:
        if one.get("name")==name:
            number = int(one.get("id",0))
    if number==0:
        print(name)
    return number

def get_class_name(number,categories=None):
    name = None
    if not categories:
        with open(os.path.join("meta.json"), "r") as f:
            coco = json.load(f)
        categories = coco["categories"]
    for one in categories:
        if one.get("id")==number:
            name = one.get("name").replace(" ","_")
    return name

def get_image_prefix(filename):
    query = filename.split(".")[0]
    return query

def get_node_or_create(elem,key,new):
    re = get(elem, key)
    if not re or new:
        child = Element(key)
        elem.append(child)
        return child
    else:
        return re[-1]

def add_xml_element(elem,key,val,new=False):
    if(type(key)==str):
        child = Element(key)
        child.text = str(val)
        elem.append(child)
    elif type(key)==list:
        node = elem
        if(len(key))<2:
            return
        for i in key[:-1]:
            node = get_node_or_create(node,i,new)
        child = Element(key[-1])
        child.text = str(val)
        node.append(child)

def check_path_exit_or_raise_exception(*args,**kwargs):
    for i in args:
        if not os.path.exists(i):
            raise Exception("{} not found!!!".format(i))

def quick_sort(li):
    _quick_sort(li,0,len(li)-1)
def _quick_sort(li,left,right):
    if left < right:
        mid = partition(li,left,right)
        _quick_sort(li,left,mid-1)
        _quick_sort(li,mid+1,right)
def partition(li,left,right):
    i = random.randint(left,right)
    li[left],li[i]=li[i],li[left]
    tmp = li[left]
    while left < right:
        while left<right and li[right]>=tmp:
            right -= 1
        li[left]=li[right]
        while left < right and li[left]<= tmp:
            left += 1
        li[right] = li[left]
    li[left] = tmp
    return left

map_path = {}
pbar = None
def get_image_name_list(src_path):
    src_list = os.listdir(src_path)
    name_list = []
    for i in src_list:
        res = gen_pattern.match(i)
        if res:
            name_list.append(res.groups()[0]+res.groups()[1])
    print("start to process %s picture"%len(name_list))
    global pbar
    pbar = pyprind.ProgBar(len(name_list),monitor=True)
    return name_list

index=0
def one_voc_format_to_json_format(src_path,file_path,image_id):
    file_path = os.path.join(src_path,file_path)
    tree = ET.parse(file_path)
    root = tree.getroot()
    filename = get_value(root, "filename")
    height = get_value(root, "size/height")
    width = get_value(root, "size/width")
    depth = get_value(root, "size/depth")
    json_dict = {"images": [{"file_name": str(image_id)+'.jpg', "height": height, "width": width, "id": image_id,
                             "license": 2, "coco_url": None, "data_captured": None, "flickr_url": None}],
                 "annotations": []
                 }
    for one in get(root, "object"):
        name = get_value(one, "name")
        pose = get_value(one, "pose")
        xmin = get_value(one, "bndbox/xmin")
        ymin = get_value(one, "bndbox/ymin")
        xmax = get_value(one, "bndbox/xmax")
        ymax = get_value(one, "bndbox/ymax")
        global index
        index +=1
        json_dict["annotations"].append(
            {"segmentation": [], "area": (xmax - xmin) * (ymax - ymin), "iscrowd": 0, "image_id": image_id,
             "bbox": [xmin, ymin, xmax - xmin, ymax - ymin], "category_id": get_class_number(name), "id": index}
        )
    return json_dict

def voc_format_to_json_format(src_path,dir_path):
    image_id_list = []
    if not os.path.exists(os.path.join(dir_path,"images")):
        os.mkdir(os.path.join(dir_path,"images"))
    for image_id in get_image_name_list(src_path):
        image_id_list.append(image_id)
        json_dict = one_voc_format_to_json_format(src_path,image_id+".xml",image_id)
        dir_file = os.path.join(dir_path, "images", str(image_id) + ".json")
        with open(dir_file, "w+") as f:
            f.write(json.dumps(json_dict,indent=4, separators=(',', ':')))
        pbar.update()
    with open(os.path.join(dir_path,"list.json"),"w") as f:
        f.write(json.dumps({"ImgIDs":image_id_list},indent=4, separators=(',', ':')))

def one_json_format_to_voc_format(coco_dict,new_image_name,dir_path,categories=None):
    elem = Element("annotation")
    filename = coco_dict.get("images")[0].get("file_name")
    height = coco_dict.get("images")[0].get("height")
    width = coco_dict.get("images")[0].get("width")
    add_xml_element(elem, "folder", dir_path.split("/")[-1])
    add_xml_element(elem, "filename", new_image_name)
    add_xml_element(elem, "path", os.path.join(dir_path,new_image_name))
    add_xml_element(elem, ["source", "database"], "Unkonwn")
    add_xml_element(elem, ["size", "height"], height)
    add_xml_element(elem, ["size", "width"], width)
    add_xml_element(elem, ["size", "depth"], 3)
    add_xml_element(elem, "segmented", 0)
    for one in coco_dict.get("annotations"):
        add_xml_element(elem, ["object", "name"], get_class_name(int(one.get("category_id")),categories), True)
        add_xml_element(elem, ["object", "pose"], "Unspecified")
        add_xml_element(elem, ["object", "truncated"], 0)
        add_xml_element(elem, ["object", "difficult"], 0)
        add_xml_element(elem, ["object", "bndbox", "xmin"], int(one.get("bbox")[0]))
        add_xml_element(elem, ["object", "bndbox", "ymin"], int(one.get("bbox")[1]))
        add_xml_element(elem, ["object", "bndbox", "xmax"], int(one.get("bbox")[2] + one.get("bbox")[0]))
        add_xml_element(elem, ["object", "bndbox", "ymax"], int(one.get("bbox")[3] + one.get("bbox")[1]))
    return elem

def json_format_to_voc_format(src_path,dir_path):
    for image_id in get_image_name_list(src_path):
        file_path = os.path.join(src_path, image_id+".json")
        with open(file_path,"r") as f:
            coco_dict = json.load(f)
        elem = one_json_format_to_voc_format(coco_dict,image_id+".jpg",dir_path)
        dir_file = os.path.join(dir_path, str(image_id) + ".xml")
        with open(dir_file,"w+") as f:
            f.write(minidom.parseString(tostring(elem)).toprettyxml().replace('<?xml version="1.0" ?>\n', ""))
        pbar.update()

def check_anno_image_number(voc_anno_path,voc_image_path):
    anno_list = os.listdir(voc_anno_path)
    image_list = os.listdir(voc_image_path)
    if(len(anno_list)!=len(image_list)):
        raise Exception("anno number not equal image number")

def get_dir_path_max_num(dir_path,prefix):
    if not os.path.exists(dir_path):
        os.mkdir(dir_path)
    dir_list = os.listdir(dir_path)
    if not os.path.exists(dir_path):
        os.mkdir(dir_path)
    max_num = 0
    pbar = pyprind.ProgBar(len(dir_list), monitor=True,title="counting dir path on specified prefix {} number".format(prefix))
    for i in dir_list:
        res = gen_pattern.match(i)
        if res:
            if res.groups()[0] != prefix:
                continue
            num = int(res.groups()[1])
            if num > max_num:
                max_num = num
        pbar.update()
    return max_num

def gen_image_name_list(voc_anno_path,voc_image_path,json_anno_path,json_image_path,prefix,args):
    src_list = os.listdir(voc_anno_path)
    max_num = get_dir_path_max_num(json_anno_path,prefix)
    name_list = []
    pb = pyprind.ProgBar(len(src_list),monitor=True,title="counting src path specified prefix {} number".format(prefix))
    for one in src_list:
        res = gen_pattern.match(one)
        if res:
            max_num += 1
            image_id = one.split('.')[0]
            new_image_path =prefix+str(max_num)+".jpg"
            if args and not args.ignore_image:
                shutil.copyfile(os.path.join(voc_image_path,str(image_id)+".jpg"), os.path.join(json_image_path,new_image_path))
            new_anno_name = prefix + str(max_num)
            name_list.append(new_anno_name)
            map_path[new_anno_name] = one
        pb.update()
    print("start to process %s picture"%len(name_list))
    global pbar
    pbar = pyprind.ProgBar(len(name_list),monitor=True,title="converting".format(prefix))
    return name_list

def merge_voc_dataset_to_json_dataset(voc_anno_path,voc_image_path,json_path,prefix="",args=None):
    check_anno_image_number(voc_anno_path,voc_image_path)
    image_id_list = []
    json_anno_path = os.path.join(json_path,"images")
    if not os.path.exists(json_anno_path):
        os.makedirs(json_anno_path,exist_ok=True)
    for image_id in gen_image_name_list(voc_anno_path,voc_image_path,json_anno_path,json_anno_path,prefix,args):
        image_id_list.append(image_id)
        json_dict = one_voc_format_to_json_format(voc_anno_path,map_path[image_id], image_id)
        dir_file = os.path.join(json_path, "images", str(image_id) + ".json")
        with open(dir_file, "w+") as f:
            f.write(json.dumps(json_dict,indent=4, separators=(',', ':')))
        pbar.update()
    if os.path.exists(os.path.join(json_path, "list.json")):
        with open(os.path.join(json_path, "list.json"), "r") as f:
            ImgIDs = json.load(f)["ImgIDs"]
    else:
        ImgIDs = []
    ImgIDs.extend(image_id_list)
    with open(os.path.join(json_path,"list.json"),"w") as f:
        f.write(json.dumps({"ImgIDs":ImgIDs},indent=4, separators=(',', ':')))
    shutil.copyfile("./meta.json",os.path.join(json_path,"meta.json"))

def merge_json_dataset_to_voc_dataset(json_path,voc_anno_path,voc_image_path,prefix="",args=None):
    if not os.path.exists(voc_image_path):
        os.mkdir(voc_image_path)
    json_anno_path = os.path.join(json_path, "images")
    for image_id in gen_image_name_list(json_anno_path,json_anno_path,voc_anno_path,voc_image_path, prefix,args):
        file_path = os.path.join(json_anno_path,map_path[image_id])
        with open(file_path,"r") as f:
            coco_dict = json.load(f)
        elem = one_json_format_to_voc_format(coco_dict,image_id+".jpg",voc_image_path)
        dir_file = os.path.join(voc_anno_path, str(image_id) + ".xml")
        with open(dir_file,"w+") as f:
            f.write(minidom.parseString(tostring(elem)).toprettyxml().replace('<?xml version="1.0" ?>\n', ""))
        pbar.update()

def get_exists_coco_max_num(coco_output_path,coco,prefix):
    max_num = 0
    old_coco = COCO(coco_output_path)
    coco["info"] = old_coco.dataset.get('info', [])
    coco["licenses"] = old_coco.dataset.get('licenses', [])
    coco["type"] =  old_coco.dataset.get('type', "instance")
    coco["categories"] =  old_coco.dataset.get('categories')
    ImgIDs = list(old_coco.imgs.keys())
    pbar = pyprind.ProgBar(len(ImgIDs), monitor=True, title="counting exist coco specified prefix {} number".format(prefix))
    for ImgID in ImgIDs:
        coco["images"].extend(old_coco.loadImgs([ImgID]))
        global index
        old_anno = old_coco.loadAnns(old_coco.getAnnIds(imgIds=[ImgID]))
        for i in old_anno:
            if index < i["id"]:
                index = i["id"]
        coco["annotations"].extend(old_anno)
        res = number_pattern.match(str(ImgID))
        if (res):
            if res.groups()[0] == prefix:
                num = int(res.groups()[1])
                if num > max_num:
                    max_num = num
        pbar.update()
    return max_num

def merge_voc_dataset_to_coco_dataset(voc_anno_path,voc_image_path,coco_output_path,coco_image_path,prefix="",args=None):
    max_num = 0
    if os.path.exists(coco_output_path):
        coco = {"images": [], "annotations": []}
        max_num = get_exists_coco_max_num(coco_output_path,coco,prefix)
    else:
        with open("meta.json","r") as f:
            coco = json.load(f)
            coco["images"]=[]
            coco["annotations"]=[]
    src_list = os.listdir(voc_anno_path)
    global pbar
    pbar = pyprind.ProgBar(len(src_list),monitor=True,title="converting voc to coco")
    for one in src_list:
        if gen_pattern.match(one):
            max_num += 1
            image_id = one.split('.')[0]
            new_image_id = prefix+str(max_num)
            json_dict = one_voc_format_to_json_format(voc_anno_path,one,new_image_id)
            coco["images"].extend(json_dict["images"])
            coco["annotations"].extend(json_dict["annotations"])
            if args and not args.ignore_image:
                shutil.copyfile(os.path.join(voc_image_path, str(image_id) + ".jpg"),os.path.join(coco_image_path,str(new_image_id)+".jpg"))
            pbar.update()
    with open(coco_output_path, "w") as f:
        f.write(json.dumps(coco, indent=4, separators=(',', ':')))

def get_file_name_from_coco(li,image_id):
    for i in li:
        if i.get("id")==image_id:
            return i.get("file_name")

def merge_coco_to_voc_dataset(coco_file_path,coco_image_path,voc_anno_path,voc_image_path,prefix="",args=None):
    if not os.path.exists(voc_image_path):
        os.mkdir(voc_image_path)
    coco = COCO(coco_file_path)
    categories = coco.dataset.get('categories')
    ImgIDs = list(coco.imgs.keys())
    global pbar
    pbar = pyprind.ProgBar(len(ImgIDs),monitor=True,title="converting coco to voc")
    max_num = get_dir_path_max_num(voc_anno_path, prefix)
    for ImgID in ImgIDs:
        max_num += 1
        new_image_id = prefix+str(max_num)
        json_dict = {}
        json_dict["images"] = coco.loadImgs([ImgID])
        json_dict["annotations"] = coco.loadAnns(coco.getAnnIds(imgIds=[ImgID]))
        old_image_name = get_file_name_from_coco(json_dict["images"], ImgID)
        elem = one_json_format_to_voc_format(json_dict, new_image_id + ".jpg",voc_image_path,categories)
        dir_file = os.path.join(voc_anno_path, new_image_id + ".xml")
        if not os.path.exists(os.path.join(coco_image_path,old_image_name)):
            print(os.path.join(coco_image_path,old_image_name),"not exists")
        else:
            with open(dir_file, "w+") as f:
                f.write(minidom.parseString(tostring(elem)).toprettyxml().replace('<?xml version="1.0" ?>\n', ""))
            if args and not args.ignore_image:
                shutil.copyfile(os.path.join(coco_image_path,old_image_name),os.path.join(voc_image_path,new_image_id+".jpg"))
        pbar.update()

def merge_coco_to_json_dataset(coco_file_path,coco_image_path,json_path,prefix="",args=None):
    json_anno_path = os.path.join(json_path, "images")
    if not os.path.exists(json_anno_path):
        os.makedirs(os.path.join(json_anno_path))
    coco = COCO(coco_file_path)
    meta_json_dict = {
        "info": coco.dataset.get('info', []),
        "licenses": coco.dataset.get('licenses', []),
        "type": coco.dataset.get('type', "instance"),
        "categories": coco.dataset.get('categories')}
    with open(os.path.join(json_path, "meta.json") , "w") as f:
        f.write(json.dumps(meta_json_dict,indent=4, separators=(',', ':')))
    ImgIDs = list(coco.imgs.keys())
    global pbar
    pbar = pyprind.ProgBar(len(ImgIDs),monitor=True,title="converting coco to json")
    max_num = get_dir_path_max_num(json_anno_path, prefix)
    if os.path.exists(os.path.join(json_path, "list.json")):
        with open(os.path.join(json_path, "list.json"), "r") as f:
            new_image_id_list = json.load(f)["ImgIDs"]
    else:
        new_image_id_list = []
    for ImgID in ImgIDs:
        max_num += 1
        new_image_id = prefix + str(max_num)
        new_image_id_list.append(new_image_id)
        json_dict = {}
        json_dict["images"] = coco.loadImgs([ImgID])
        json_dict["annotations"] = coco.loadAnns(coco.getAnnIds(imgIds=[ImgID]))
        with open(os.path.join(json_path, "images", "{}.json".format(new_image_id)), "w") as f:
            f.write(json.dumps(json_dict, indent=4, separators=(',', ':')))
        img_path = os.path.join(coco_image_path, json_dict["images"][0]["file_name"])
        if os.path.exists(img_path):
            if args and not args.ignore_image:
                shutil.copyfile(img_path, os.path.join(json_path, "images", "{}.jpg".format(new_image_id)))
        else:
            print("'{}' file does not exist.".format(img_path))
        pbar.update()
    with open(os.path.join(json_path, "list.json") , "w") as f:
        f.write(json.dumps({"ImgIDs":new_image_id_list},indent=4, separators=(',', ':')))

def merge_json_to_coco_dataset(json_path,coco_file_path,coco_image_path,prefix="",args=None):
    max_num = 0
    if not os.path.exists(coco_image_path):
        os.makedirs(coco_image_path)
    if os.path.exists(coco_file_path):
        coco = {"images": [], "annotations": []}
        max_num = get_exists_coco_max_num(coco_file_path,coco,prefix)
    else:
        with open("meta.json","r") as f:
            coco = json.load(f)
            coco["images"] = []
            coco["annotations"] = []
    with open(os.path.join(json_path, "list.json"), "r") as f:
        ImgIDs = json.load(f)["ImgIDs"]
    global pbar
    pbar = pyprind.ProgBar(len(ImgIDs),monitor=True,title="converting json to coco")
    for ImgID in ImgIDs:
        max_num += 1
        new_image_id = prefix + str(max_num)
        with open(os.path.join(json_path, 'images', "{}.json".format(ImgID)), "r") as f:
            json_dict = json.load(f)
        json_dict["images"][0]["file_name"] = "{}.jpg".format(new_image_id)
        json_dict["images"][0]["id"] = new_image_id
        for i in json_dict["annotations"]:
            i["image_id"] = new_image_id
            global index
            i["id"] = index
            index += 1
        coco["images"].extend(json_dict["images"])
        coco["annotations"].extend(json_dict["annotations"])
        source_path = os.path.join(json_path, 'images', "{}.jpg".format(ImgID))
        if args and not args.ignore_image:
            shutil.copyfile(source_path, os.path.join(coco_image_path, "{}.jpg".format(new_image_id)))
        pbar.update()
    with open(coco_file_path, "w") as f:
        f.write(json.dumps(coco, indent=4, separators=(',', ':')))

def copy_dir_by_percent(src_path,dir_path,percent=0,number=0):
    if not percent and not number:
        shutil.copytree(src_path, dir_path)
    else:
        src_list = os.listdir(src_path)
        total_len = len(src_list)
        target = 0
        if percent:
            target = int(total_len*float(percent))
        elif number:
            target = int(number)
        if target:
            if not os.path.exists(dir_path):
                os.makedirs(dir_path)
            for i in src_list[:target]:
                shutil.copyfile(os.path.join(src_path,i),os.path.join(dir_path,i))

def copy_json_by_percent(src_path,dir_path,percent=0,number=0):
    src_image_path = os.path.join(src_path,"images")
    dir_image_path = os.path.join(dir_path,"images")
    if not os.path.exists(dir_image_path):
        os.makedirs(dir_image_path)
    if not percent and not number:
        shutil.copytree(src_path, dir_path)
        shutil.copyfile(os.path.join(src_path, "list.json"), os.path.join(dir_path, "list.json"))
        shutil.copyfile(os.path.join(src_path, "meta.json"), os.path.join(dir_path, "meta.json"))
    else:
        src_list = os.listdir(src_image_path)
        total_len = len(src_list)//2
        target = 0
        current=0
        ImgIDs = []
        if percent:
            target = int(total_len * float(percent))
        elif number:
            target = int(number)
        if target:
            if not os.path.exists(dir_image_path):
                os.makedirs(dir_image_path)
            for i in src_list:
                res = gen_pattern.match(i)
                if(res):
                    current +=1
                    if(current>target):
                        break
                    image_id = res.groups()[0]+res.groups()[1]
                    image_name =image_id +".jpg"
                    shutil.copyfile(os.path.join(src_image_path, i), os.path.join(dir_image_path, i))
                    shutil.copyfile(os.path.join(src_image_path,image_name), os.path.join(dir_image_path, image_name))
                    ImgIDs.append(image_id)
            with open(os.path.join(dir_path, "list.json"), "w") as f:
                f.write(json.dumps({"ImgIDs":ImgIDs},indent=4, separators=(',', ':')))
            shutil.copyfile(os.path.join(src_path, "meta.json"), os.path.join(dir_path, "meta.json"))

def copy_voc_by_percent(src_path,dir_path,percent=0,number=0):
    src_image_path = os.path.join(src_path,"JPEGImages")
    src_anno_path = os.path.join(src_path,"Annotations")
    dir_image_path = os.path.join(dir_path, "JPEGImages")
    dir_anno_path = os.path.join(dir_path, "Annotations")
    if not percent and not number:
        shutil.copytree(src_image_path, dir_image_path)
        shutil.copytree(src_anno_path, dir_anno_path)
    else:
        src_list = os.listdir(src_anno_path)
        total_len = len(src_list)
        target = 0
        current=0
        if percent:
            target = int(total_len * float(percent))
        elif number:
            target = int(number)
        if target:
            if not os.path.exists(dir_image_path):
                os.makedirs(dir_image_path)
            if not os.path.exists(dir_anno_path):
                os.makedirs(dir_anno_path)
            for i in src_list:
                res = gen_pattern.match(i)
                if(res):
                    current +=1
                    if(current>target):
                        break
                    image_id = res.groups()[0]+res.groups()[1]
                    image_name =image_id +".jpg"
                    anno_name =image_id +".xml"
                    shutil.copyfile(os.path.join(src_anno_path,anno_name), os.path.join(dir_anno_path, anno_name))
                    shutil.copyfile(os.path.join(src_image_path,image_name), os.path.join(dir_image_path, image_name))

def copy_coco_by_percent(from_file_path,from_image_path,to_file_path,to_image_path,percent=0,number=0):
    if not percent and not number:
        shutil.copytree(from_image_path, to_image_path)
        shutil.copyfile(from_file_path,to_file_path)
    else:
        if not os.path.exists(to_image_path):
            os.makedirs(to_image_path)
        coco = COCO(from_file_path)
        new_coco ={
            "info": coco.dataset.get('info', []),
            "licenses": coco.dataset.get('licenses', []),
            "type": coco.dataset.get('type', "instance"),
            "categories": coco.dataset.get('categories'),
            "images":[],
            "annotations":[]
        }
        ImgIDs = list(coco.imgs.keys())
        total_len = len(ImgIDs) // 2
        target = 0
        current = 0
        if percent:
            target = int(total_len * float(percent))
        elif number:
            target = int(number)
        if target:
            for ImgID in ImgIDs:
                new_coco["images"].extend(coco.loadImgs([ImgID]))
                new_coco["annotations"].extend(coco.loadAnns(coco.getAnnIds(imgIds=[ImgID])))
                shutil.copyfile(os.path.join(from_image_path,"{}.jpg".format(ImgID)), os.path.join(to_image_path,"{}.jpg".format(ImgID)))
                current +=1
                if current>=target:
                    break
            with open(to_file_path, "w") as f:
                f.write(json.dumps(new_coco,indent=4, separators=(',', ':')))

def remove_json_by_prefix(json_path,prefix=""):
    json_anno_path = os.path.join(json_path,"images")
    with open(os.path.join(json_path, "list.json"), "r") as f:
        ImgIDs = json.load(f)["ImgIDs"]
    new_images = ImgIDs.copy()
    pbar = pyprind.ProgBar(len(ImgIDs), monitor=True, title="removing coco by prefix {}".format(prefix))
    for ImgID in ImgIDs:
        if str(ImgID).startswith(prefix):
            new_images.remove(ImgID)
            os.remove(os.path.join(json_anno_path,"{}.jpg".format(ImgID)))
            os.remove(os.path.join(json_anno_path,"{}.json".format(ImgID)))
        pbar.update()
    with open(os.path.join(json_path, "list.json") , "w") as f:
        f.write(json.dumps({"ImgIDs":new_images},indent=4, separators=(',', ':')))

def remove_voc_by_prefix(voc_path,prefix=""):
    voc_anno_path = os.path.join(voc_path,"Annotations")
    voc_image_path = os.path.join(voc_path,"JPEGImages")
    src_list = os.listdir(voc_anno_path)
    pbar = pyprind.ProgBar(len(src_list), monitor=True, title="removing coco by prefix {}".format(prefix))
    for i in src_list:
        if i.startswith(prefix):
            os.remove(os.path.join(voc_anno_path,i))
            res = gen_pattern.match(i)
            if res:
                image_id = res.groups()[0]+res.groups()[1]
                os.remove(os.path.join(voc_image_path, "{}.jpg".format(image_id)))
        pbar.update()

def remove_coco_by_prefix(coco_file_path,coco_image_path,prefix=""):
    coco = {"images": [], "annotations": []}
    old_coco = COCO(coco_file_path)
    coco["info"] = old_coco.dataset.get('info', [])
    coco["licenses"] = old_coco.dataset.get('licenses', [])
    coco["type"] = old_coco.dataset.get('type', "instance")
    coco["categories"] = old_coco.dataset.get('categories')
    ImgIDs = list(old_coco.imgs.keys())
    pbar = pyprind.ProgBar(len(ImgIDs), monitor=True, title="removing coco by prefix {}".format(prefix))
    for ImgID in ImgIDs:
        if not str(ImgID).startswith(prefix):
            coco["images"].extend(old_coco.loadImgs([ImgID]))
        else:
            os.remove(os.path.join(coco_image_path, "{}.jpg".format(ImgID)))
        pbar.update()
    with open(coco_file_path, "w") as f:
        f.write(json.dumps(coco, indent=4, separators=(',', ':')))

def annotations_to_voc_xml_file(annotations,width,height,outputfilepath,override=False):
    dir_path,filename = outputfilepath.rsplit("/",1)
    image_name = filename.split(".")[0]+".jpg"
    image_path = os.path.join(dir_path,image_name)
    elem = Element("annotation")
    add_xml_element(elem, "folder", dir_path.split("/")[-1])
    add_xml_element(elem, "filename", image_name)
    add_xml_element(elem, "path", image_path)
    add_xml_element(elem, ["source", "database"], "Unkonwn")
    add_xml_element(elem, ["size", "height"], height)
    add_xml_element(elem, ["size", "width"], width)
    add_xml_element(elem, ["size", "depth"], 3)
    add_xml_element(elem, "segmented", 0)
    for annotaton in annotations:
        label,xmin,ymin,xmax,ymax = annotaton
        add_xml_element(elem, ["object", "name"], label, True)
        add_xml_element(elem, ["object", "pose"], "Unspecified")
        add_xml_element(elem, ["object", "truncated"], 0)
        add_xml_element(elem, ["object", "difficult"], 0)
        add_xml_element(elem, ["object", "bndbox", "xmin"], xmin)
        add_xml_element(elem, ["object", "bndbox", "ymin"], ymin)
        add_xml_element(elem, ["object", "bndbox", "xmax"], xmax)
        add_xml_element(elem, ["object", "bndbox", "ymax"], ymax)
    if os.path.exists(outputfilepath):
        if override:
            with open(outputfilepath, "w+") as f:
                f.write(minidom.parseString(tostring(elem)).toprettyxml().replace('<?xml version="1.0" ?>\n', ""))
    else:
        os.makedirs(dir_path,exist_ok=True)
        with open(outputfilepath, "w+") as f:
            f.write(minidom.parseString(tostring(elem)).toprettyxml().replace('<?xml version="1.0" ?>\n', ""))

def count_voc_per_class_and_bbox_numbers(voc_path,prefix=""):
    dir_path = os.path.join(voc_path,"Annotations")
    train_path = os.path.join(voc_path,"ImageSets","Main","train.txt")
    val_path = os.path.join(voc_path,"ImageSets","Main","val.txt")
    test_path = os.path.join(voc_path,"ImageSets","Main","test.txt")
    if os.path.exists(train_path):
        with open(train_path,"r") as f:
            tmp=[]
            for i in f:
                tmp.append(i.strip()+".xml")
        count_file_list(tmp,dir_path,prefix,"counting voc train set")
    if os.path.exists(val_path):
        with open(val_path,"r") as f:
            tmp=[]
            for i in f:
                tmp.append(i.strip()+".xml")
        count_file_list(tmp,dir_path,prefix,"counting voc val set")
    if os.path.exists(test_path):
        with open(test_path,"r") as f:
            tmp=[]
            for i in f:
                tmp.append(i.strip()+".xml")
        count_file_list(tmp,dir_path,prefix,"counting voc test set")
    if not os.path.exists(train_path) and not os.path.exists(val_path) and not os.path.exists(test_path):
        dir_list = os.listdir(dir_path)
        count_file_list(dir_list, dir_path, prefix,"counting voc all set")

def count_file_list(file_name_list,dir_path,prefix,title):
    details = {}
    global pbar
    total_count = 0
    pbar = pyprind.ProgBar(len(file_name_list),title=title)
    for i in file_name_list:
        res = gen_pattern.match(i)
        if res:
            if prefix and  res.groups()[0] != prefix:
                pbar.update()
                continue
            total_count += 1
            json_dict = one_voc_format_to_json_format(dir_path,i, res.groups()[0]+res.groups()[1])
            for one in json_dict.get("annotations"):
                details.setdefault(one["category_id"], {"image_counts":set(), "bbox_count": 0})
                details[one["category_id"]]["bbox_count"] += 1
                details[one["category_id"]]["image_counts"].add(one["image_id"])
        pbar.update()
    for k,v in details.items():
        details[k]["image_counts"]=len(details[k]["image_counts"])
    for j in sorted(details.items(),key=lambda x:x[0]):
        print('{:<20s} {}'.format(get_class_name(j[0]),json.dumps(j[1])))
    print("total images count:",total_count)

def count_json_per_class_and_bbox_numbers(json_path,prefix=""):
    dir_path = os.path.join(json_path,"images")
    dir_list = os.listdir(dir_path)
    details = {}
    global pbar
    pbar = pyprind.ProgBar(len(dir_list),title="counting json")
    for i in dir_list:
        res = gen_pattern.match(i)
        if res:
            if prefix and res.groups()[0] != prefix:
                pbar.update()
                continue
            with open(os.path.join(dir_path,i),'r') as f:
                json_dict = json.load(f)
            for one in json_dict.get("annotations"):
                details.setdefault(one["category_id"], {"image_counts":set(), "bbox_count": 0})
                details[one["category_id"]]["bbox_count"] += 1
                details[one["category_id"]]["image_counts"].add(one["image_id"])
        pbar.update()
    for k,v in details.items():
        details[k]["image_counts"]=len(details[k]["image_counts"])
    for j in sorted(details.items(),key=lambda x:x[0]):
        print('{:<20s} {}'.format(get_class_name(j[0]),json.dumps(j[1])))

def count_coco_per_class_and_bbox_numbers(coco_file_path,prefix=""):
    details = {}
    global pbar
    coco = COCO(coco_file_path)
    ImgIDs = list(coco.imgs.keys())
    global pbar
    pbar = pyprind.ProgBar(len(ImgIDs),title="counting coco")
    for ImgID in ImgIDs:
        json_dict = {}
        json_dict["images"] = coco.loadImgs([ImgID])
        json_dict["annotations"] = coco.loadAnns(coco.getAnnIds(imgIds=[ImgID]))
        image_name = get_file_name_from_coco(json_dict["images"], ImgID)
        res = gen_pattern.match(image_name)
        if res:
            if prefix and res.groups()[0] != prefix:
                pbar.update()
                continue
        for one in json_dict.get("annotations"):
            details.setdefault(one["category_id"], {"image_counts":set(), "bbox_count": 0})
            details[one["category_id"]]["bbox_count"] += 1
            details[one["category_id"]]["image_counts"].add(one["image_id"])
        pbar.update()
    for k,v in details.items():
        details[k]["image_counts"]=len(details[k]["image_counts"])
    for j in sorted(details.items(),key=lambda x:x[0]):
        print('{:<20s} {}'.format(get_class_name(j[0]),json.dumps(j[1])))

def run_command(args, command, nargs, parser):
    if command == "json-to-voc":
        if len(nargs) != 2:
            parser.print_help()
            print("json-to-voc [json_dir] [voc_dir]")
        else:
            json_format_to_voc_format(nargs[0], nargs[1])
    elif command == "voc-to-json":
        if len(nargs) != 2:
            parser.print_help()
            print("voc-to-json [voc_dir] [json_dir]")
        else:
            voc_format_to_json_format(nargs[0], nargs[1])
    elif command == "remove-json":
        if len(nargs) != 1:
            parser.print_help()
            print("\n [--prefix xxx] remove-json [json_dir]")
        else:
            remove_json_by_prefix(nargs[0], prefix=args.prefix)
    elif command == "remove-voc":
        if len(nargs) != 1:
            parser.print_help()
            print("\n [--prefix xxx] remove-voc [voc_dir]")
        else:
            remove_voc_by_prefix(nargs[0], prefix=args.prefix)
    elif command == "remove-coco":
        if len(nargs) != 2:
            parser.print_help()
            print("\n [--prefix xxx] remove-coco [coco_file_path] [coco_image_path]")
        else:
            remove_coco_by_prefix(nargs[0],nargs[1], prefix=args.prefix)
    elif command == "copy":
        if len(nargs) != 2:
            parser.print_help()
            print("\n [--percent 0.1] [--number 100] copy [from_path] [to_path]")
        else:
            copy_dir_by_percent(nargs[0], nargs[1],percent=args.percent,number=args.number)
    elif command == "copy-json":
        if len(nargs) != 2:
            parser.print_help()
            print("\n [--percent 0.1] [--number 100] copy-json [from_path] [to_path]")
        else:
            copy_json_by_percent(nargs[0], nargs[1],percent=args.percent,number=args.number)
    elif command == "copy-voc":
        if len(nargs) != 2:
            parser.print_help()
            print("\n [--percent 0.1] [--number 100] copy-json [from_path] [to_path]")
        else:
            copy_voc_by_percent(nargs[0], nargs[1],percent=args.percent,number=args.number)
    elif command == "copy-coco":
        if len(nargs) != 4:
            parser.print_help()
            print("\n [--percent 0.1] [--number 100] copy-coco [from_file_path] [from_image_path] [to_file_path] [to_image_path]")
        else:
            copy_coco_by_percent(nargs[0], nargs[1], nargs[2], nargs[3],percent=args.percent,number=args.number)
    elif command == "merge-voc-to-json":
        if len(nargs) != 2:
            parser.print_help()
            print("\n [--prefix xxx] merge-voc-to-json [voc_path] [json_path]")
        else:
            check_path_exit_or_raise_exception(os.path.join(nargs[0],"Annotations"),os.path.join(nargs[0],"JPEGImages"))
            merge_voc_dataset_to_json_dataset(os.path.join(nargs[0],"Annotations"),os.path.join(nargs[0],"JPEGImages"), nargs[1],prefix=args.prefix,args=args)
    elif command == "merge-voc-to-coco":
        if len(nargs) != 3:
            parser.print_help()
            print("\n [--prefix xxx] merge-voc-to-coco [voc_path] [coco_output_file_path] [coco_img_path]")
        else:
            check_path_exit_or_raise_exception(os.path.join(nargs[0],"Annotations"), os.path.join(nargs[0],"JPEGImages"))
            merge_voc_dataset_to_coco_dataset(os.path.join(nargs[0],"Annotations"), os.path.join(nargs[0],"JPEGImages"),nargs[1],nargs[2],prefix=args.prefix,args=args)
    elif command == "merge-coco-to-voc":
        if len(nargs) != 3:
            parser.print_help()
            print("\n [--prefix xxx] merge-coco-to-voc [coco_file_path] [coco_image_path] [voc_path]")
        else:
            check_path_exit_or_raise_exception(nargs[0],nargs[1])
            merge_coco_to_voc_dataset(nargs[0],nargs[1],os.path.join(nargs[2],"Annotations"),os.path.join(nargs[2],"JPEGImages"),prefix=args.prefix,args=args)
    elif command == "merge-json-to-voc":
        if len(nargs) != 2:
            parser.print_help()
            print("\n [--prefix xxx] merge-json-to-voc [json_path] [voc_path]")
        else:
            check_path_exit_or_raise_exception(nargs[0])
            merge_json_dataset_to_voc_dataset(nargs[0],os.path.join(nargs[1],"Annotations"),os.path.join(nargs[1],"JPEGImages"),prefix=args.prefix,args=args)
    elif command == "merge-coco-to-json":
        if len(nargs) != 3:
            parser.print_help()
            print("\n [--prefix xxx] merge-coco-to-json [coco_file_path] [coco_image_path] [json_path]")
        else:
            check_path_exit_or_raise_exception(nargs[0],nargs[1])
            merge_coco_to_json_dataset(nargs[0],nargs[1],nargs[2],prefix=args.prefix,args=args)
    elif command == "merge-json-to-coco":
        if len(nargs) != 3:
            parser.print_help()
            print("\n [--prefix xxx] merge-json-to-coco [json_path] [coco_file_path] [coco_image_path]\n")
        else:
            check_path_exit_or_raise_exception(nargs[0])
            merge_json_to_coco_dataset(nargs[0],nargs[1],nargs[2],prefix=args.prefix,args=args)
    elif command == "count-voc":
        if len(nargs) != 1:
            parser.print_help()
            print("\n [--prefix xxx] count-voc [voc_path]\n")
        else:
            count_voc_per_class_and_bbox_numbers(nargs[0],prefix=args.prefix)
    elif command == "count-json":
        if len(nargs) != 1:
            parser.print_help()
            print("\n [--prefix xxx] count-json [json_path]\n")
        else:
            count_json_per_class_and_bbox_numbers(nargs[0],prefix=args.prefix)
    elif command == "count-coco":
        if len(nargs) != 1:
            parser.print_help()
            print("\n [--prefix xxx] count-coco [coco_file_path]\n")
        else:
            count_coco_per_class_and_bbox_numbers(nargs[0],prefix=args.prefix)
    else:
        parser.print_help()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(prog='label_tool.py',
                                     formatter_class=argparse.RawDescriptionHelpFormatter,
                                     description=textwrap.dedent('''\
    coco format & voc format convert.

    Command:
        copy 
            [from_path] [to_path] : copy on percent
        copy-json
            [from_path] [to_path] : copy json sample on percent
        copy-voc
            [from_path] [to_path] : copy voc sample on percent
        copy-coco
            [from_file_path] [from_image_path] [to_file_path] [to_image_path] : copy coco sample on percent
        remove-voc
            [voc_dir] : remove specify prefix part
        remove-json
            [json_dir] : remove specify prefix part
        remove-coco 
            [coco_file_path] [coco_image_path] : remove specify prefix part
        json-to-voc 
            [coco_dir] [voc_dir] : convert json annotatino to voc annotation
        voc-to-json
            [voc_dir] [coco_dir] : convert voc annotatino to json annotation
        merge-voc-to-json
            [voc_path] [json_path]: merge voc annotatino into json annotation
        merge-json-to-voc
            [json_path] [voc_path]: merge json annotatino into voc annotation
        merge-voc-to-coco
            [voc_path] [coco_output_file_path] [coco_img_path]:merge voc to coco format
        merge-coco-to-voc 
            [coco_file_path] [coco_image_path] [voc_path]:merge coco to voc format
        merge-coco-to-json 
            [coco_file_path] [coco_image_path] [json_path]:merge coco to json format
        merge-json-to-coco 
            [json_path] [coco_file_path] [coco_image_path]:merge json to coco format
      '''))
    parser.add_argument("--prefix", "-p",
                        default="",
                        help="generate file'prefix",
                        action="store"
                        )
    parser.add_argument("--ignore-image",
                        default=False,
                        help="dont copy image",
                        action="store_true"
                        )
    parser.add_argument("--percent",
                        default=0,
                        help="copy file percent",
                        action="store"
                        )
    parser.add_argument("--number","-n",
                        default=0,
                        help="copy file numbers",
                        action="store"
                        )
    parser.add_argument("command",
                        help="See above for the list of valid command")
    parser.add_argument('nargs', nargs=argparse.REMAINDER,
                        help="Additional command argument",
                        )
    args = parser.parse_args()
    command = args.command
    nargs = args.nargs
    run_command(args, command, nargs, parser)

