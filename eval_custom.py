import sys
sys.path.append('/home/minhduc/AAAAA/FPT/apring 2024/3dpanorama/DMH-Net')

import json
import os
# import ipdb
import sys

import numpy as np
import torch.nn as nn
from torch.utils.data import DataLoader
from tqdm import trange

from config import cfg
from misc.utils import pipeload
from model import DMHNet
from perspective_dataset import PerspectiveDataset
from postprocess.postprocess2 import postProcess
from torch.nn import functional as F
from easydict import EasyDict
from layout_viewer import *

import open3d

cfg = {'ROOT_DIR': '/home/minhduc/AAAAA/FPT/apring 2024/3dpanorama', 'LOCAL_RANK': 0, 'DATA': {'ROOT_DIR': '/home/minhduc/AAAAA/FPT/apring 2024/3dpanorama/DMH-Net-Implementation-web-demo/uploads', 'TYPE': 'cuboid', 'DATASET': 'PerspectiveDataset', 'PREFIX': ['pano'], 'AUGMENT': {'stretch': True, 'flip': False, 'erase': True, 'gamma': True, 'noise': True}}, 'MODEL': {'BACKBONE': {'PRIVATE_UPDOWN': False, 'PRIVATE_UP': False}, 'HOUGH': {'CLINE_TYPE': 'NEW', 'GRADUAL_LABEL': {'XY': 0.96, 'CUPDOWN': 0.96}}}, 'POST_PROCESS': {'METHOD': 'optimization', 'CPP': 0.0, 'ZPP': 0.0, 'ITER': 0, 'ITER_NZ': 1, 'DEFAULT_DISTANCE': 1.6, 'PEAK_HEIGHT': 0.2, 'PEAK_PROMINENCE': 0.0}, 'OPTIM': {'MAX_EPOCH': 1, 'TYPE': 'Adam', 'LR': 0.0001, 'BATCH_SIZE': 1}, 'TAG': 'panocontext', 'EXP_GROUP_PATH': ''}
cfg = EasyDict(cfg)
net = DMHNet(cfg, cfg.MODEL.get("BACKBONE", {}).get("NAME", "drn38"), True).to('cuda')
net = nn.DataParallel(net)
state_dict = pipeload('/home/minhduc/AAAAA/FPT/apring 2024/3dpanorama/DMH-Net/ckpt/duci/panocontext_v1.pth', map_location='cpu')["state_dict"]
net.load_state_dict(state_dict, strict=True)

def valid(filename):
    if len(os.listdir('result_json/')) != 0:
        gen3d()
        return
    net.eval()
    dataset = PerspectiveDataset(cfg, "test", filename=filename)
    dataloader = DataLoader(dataset, batch_size= 1, 
                            collate_fn=dataset.collate, )
    for inputs in dataloader:
        
        losses, results_dict = net(inputs)
        postResults = []

        for i in range(len(inputs['filename'])):
            # print(inputs.keys())
            # print(results_dict.keys())
            # print(results_dict['p_preds_xy'].shape)
            # print(results_dict['p_preds_cud'].shape)
            postResult = postProcess(cfg, inputs, results_dict, i, is_valid_mode= False)
            postResults.append(postResult)

            (_, _, _), (_, _, pred_cors), metric = postResult
            uv = pred_cors.cpu().numpy() / inputs["e_img"].shape[-1:-3:-1]
            uv = [[o.item() for o in pt] for pt in uv]

            JSON_DIR = "result_json"
            os.makedirs(JSON_DIR, exist_ok=True)
            with open(os.path.join(JSON_DIR, inputs["filename"][0] + ".json"), "w") as f:
                print({"uv": uv, "3DIoU": metric["3DIoU"].item()})
                json.dump({"uv": uv, "3DIoU": metric["3DIoU"].item()}, f)
    gen3d()

def gen3d():
    # Reading source (texture img, cor_id txt)
    path = 'uploads/test/img/'
    print(os.listdir(path))
    name = os.listdir(path)[0]
    equirect_texture = np.array(Image.open(path + name)) / 255.0
    H, W = equirect_texture.shape[:2]
    print(H, W)
    with open('result_json/' + name + '.json') as f:
        inferenced_result = json.load(f)
    
    cor_id = np.array(inferenced_result['uv'], np.float32)
    cor_id[:, 0] *= W
    cor_id[:, 1] *= H

    ceil_floor_mask = create_ceiling_floor_mask(cor_id, H, W)

    # Convert cor_id to 3d xyz
    N = len(cor_id) // 2
    floor_z = -1.6
    floor_xy = np_coor2xy(cor_id[1::2], floor_z, W, H, floorW=1, floorH=1)
    c = np.sqrt((floor_xy**2).sum(1))
    v = np_coory2v(cor_id[0::2, 1], H)
    ceil_z = (c * np.tan(v)).mean()

    # Prepare
    if not False:
        assert N == len(floor_xy)
        wf_points = [[-x, y, floor_z] for x, y in floor_xy] +\
                    [[-x, y, ceil_z] for x, y in floor_xy]
        wf_lines = [[i, (i+1)%N] for i in range(N)] +\
                [[i+N, (i+1)%N+N] for i in range(N)] +\
                [[i, i+N] for i in range(N)]
        wf_colors = [[0, 1, 0] if i % 2 == 0 else [0, 0, 1] for i in range(N)] +\
                    [[0, 1, 0] if i % 2 == 0 else [0, 0, 1] for i in range(N)] +\
                    [[1, 0, 0] for i in range(N)]
        wf_line_set = open3d.geometry.LineSet()
        wf_line_set.points = open3d.utility.Vector3dVector(wf_points)
        wf_line_set.lines = open3d.utility.Vector2iVector(wf_lines)
        wf_line_set.colors = open3d.utility.Vector3dVector(wf_colors)

    # Warp each wall
    all_rgb, all_xyz = warp_walls(equirect_texture, floor_xy, floor_z, ceil_z,
                                80)

    # Warp floor and ceiling
    if not False or not False:
        fi, fp, ci, cp = warp_floor_ceiling(equirect_texture,
                                            ceil_floor_mask,
                                            floor_xy,
                                            floor_z,
                                            ceil_z,
                                            ppm=80)

        if not False:
            all_rgb.extend(fi)
            all_xyz.extend(fp)

        if not False:
            all_rgb.extend(ci)
            all_xyz.extend(cp)

    all_xyz = np.array(all_xyz)
    all_rgb = np.array(all_rgb)

    all_xyz = all_xyz * np.array([-1,1,1])

    # Filter occluded points
    occlusion_mask, reord_idx = create_occlusion_mask(all_xyz)
    all_xyz = all_xyz[reord_idx][~occlusion_mask]
    all_rgb = all_rgb[reord_idx][~occlusion_mask]
    print(all_xyz.shape)
    print(all_rgb.shape)

    # Launch point cloud viewer
    print('Showing %d of points...' % len(all_rgb))
    pcd = open3d.geometry.PointCloud()
    pcd.points = open3d.utility.Vector3dVector(all_xyz)
    pcd.colors = open3d.utility.Vector3dVector(all_rgb)

    # Visualize result

    tobe_visualize = [pcd]
    if not False:
        # tobe_visualize.append(wf_line_set)
        line_mesh1 = LineMesh(wf_points, wf_lines, wf_colors, radius=0.04)
        line_mesh1_geoms = line_mesh1.cylinder_segments
        tobe_visualize.extend(line_mesh1_geoms)

    open3d.visualization.RenderOption.line_width = 15.0
    open3d.visualization.draw_plotly(tobe_visualize, height=800, width=1200)

