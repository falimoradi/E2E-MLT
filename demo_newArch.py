'''
Created on Aug 25, 2017

@author: busta
'''

import cv2, os
import numpy as np

from nms import get_boxes

from models import ModelResNetSep2, ModelMLTRCTW
import net_utils

from ocr_utils import ocr_image
from data_gen import draw_box_points
import torch

import argparse

from PIL import Image
from PIL import ImageFont
from PIL import ImageDraw

from torch.nn import Conv2d

import codecs


f = codecs.open('codec_mine2.txt', 'r', encoding='utf-8')
codec = f.readlines()[0]
f.close()

def resize_image(im, max_size = 1585152, scale_up=True):

  if scale_up:
    image_size = [im.shape[1] * 3 // 32 * 32, im.shape[0] * 3 // 32 * 32]
  else:
    image_size = [im.shape[1] // 32 * 32, im.shape[0] // 32 * 32]
  while image_size[0] * image_size[1] > max_size:
    image_size[0] /= 1.2
    image_size[1] /= 1.2
    image_size[0] = int(image_size[0] // 32) * 32
    image_size[1] = int(image_size[1] // 32) * 32


  resize_h = int(image_size[1])
  resize_w = int(image_size[0])


  scaled = cv2.resize(im, dsize=(resize_w, resize_h))
  return scaled, (resize_h, resize_w)


if __name__ == '__main__':

  parser = argparse.ArgumentParser()
  parser.add_argument('-cuda', type=int, default=1)
  parser.add_argument('-model', default='e2e-mlt.h5')
  parser.add_argument('-segm_thresh', default=0.5)

  font2 = ImageFont.truetype("Arial-Unicode-Regular.ttf", 18)

  args = parser.parse_args()

  net = ModelMLTRCTW(attention=True)
  net.conv11 = Conv2d(256, 150, (1, 1), padding=(0,0))
  net_utils.load_net(args.model, net)
  net = net.eval()

  if args.cuda:
    print('Using cuda ...')
    net = net.cuda()

#   cap = cv2.VideoCapture(0)
#   cap.set(cv2.CAP_PROP_AUTOFOCUS, 1)
#   ret, im = cap.read()

  # frame_no = 0
  imgs = os.listdir()
  imgs = [im for im in imgs if im.lower().endswith('.jpg')]
  
  with torch.no_grad():
    for im_name in imgs:
      annot = ''
#       ret, im = cap.read()
      im = cv2.imread(im_name)
      # im = cv2.cvtColor(im, cv2.COLOR_BGR2RGB)

      if True:
        im_resized, (ratio_h, ratio_w) = resize_image(im, scale_up=False)
        images = np.asarray([im_resized], dtype=np.float)
        images /= 128
        images -= 1
        im_data = net_utils.np_to_variable(images, is_cuda=args.cuda).permute(0, 3, 1, 2)
        seg_pred, rboxs, angle_pred, features = net(im_data)

        rbox = rboxs[0].data.cpu()[0].numpy()
        rbox = rbox.swapaxes(0, 1)
        rbox = rbox.swapaxes(1, 2)

        angle_pred = angle_pred[0].data.cpu()[0].numpy()


        segm = seg_pred[0].data.cpu()[0].numpy()
        segm = segm.squeeze(0)

        draw2 = np.copy(im_resized)
        boxes =  get_boxes(segm, rbox, angle_pred, args.segm_thresh)

        img = Image.fromarray(draw2)
        draw = ImageDraw.Draw(img)

        #if len(boxes) > 10:
        #  boxes = boxes[0:10]

        out_boxes = []
        for box in boxes:

          pts  = box[0:8]
          pts = pts.reshape(4, -1)

          det_text, conf, dec_s = ocr_image(net, codec, im_data, box)
          if len(det_text) == 0:
            continue

          width, height = draw.textsize(det_text, font=font2)
          center =  [box[0], box[1]]
          draw.text((center[0], center[1]), det_text, fill = (0,255,0),font=font2)
          out_boxes.append(box)
          print(det_text)
          
          pts = pts.reshape((1, 8))
          for pt in pts[0]:
            annot += str(pt) + ','
          annot += det_text + '\n'

        im = np.array(img)
        for box in out_boxes:
          pts = box[0:8]
          pts = pts.reshape(4, -1)
          draw_box_points(im, pts, color=(0, 255, 0), thickness=1)

        # cv2.imshow('img', im)
        # cv2.waitKey(10)
        cv2.imwrite('{}_res.jpg'.format(im_name.split('.')[0]), im)
        with codecs.open('{}.txt'.format(im_name.split('.')[0]), 'w', 'utf-8') as f:
          f.write(annot)

