import cv2
import torch
import warnings
import numpy as np
from libs.bbox import BoundBox
from PySide6.QtCore import QObject
import torchvision.transforms.v2 as v2
from libs.ADPKDModel import ADPKDModel, ADPKDSegmentationModel
warnings.filterwarnings("ignore")
torch.set_num_threads(8)
print(torch.get_num_threads())
torch.set_float32_matmul_precision('medium')


class ADPKDDetector(QObject):

    def __init__(self, checkpoint, size=512):
        super().__init__()
        self.size = size
        self.device = 'cpu'
        if torch.cuda.is_available():
            self.device = 'cuda'
        elif torch.backends.mps.is_available():
            self.device = 'mps'
        print(f'Detector using {self.device} as computing device')
        print(checkpoint)
        self.model = ADPKDModel.load_from_checkpoint(checkpoint)
        if self.device == 'cpu':
            self.model = self.model.eval()
        else:
            self.model = self.model.eval().half().to(self.device)
        self.transform = v2.Compose([
            v2.ToPILImage(),
            v2.Resize((self.size, self.size)),
            v2.ToTensor()
        ])
        self.offset = 0
        self.score_threshold = 0.90

    def predict(self, img: np.array, img_size=(1920, 2560)):
        boxes = list()
        if isinstance(img, np.ndarray):
            tensor_img: torch.Tensor = self.transform(img)
            if self.device == 'cpu':
                y_hat: torch.Tensor = self.model(tensor_img.unsqueeze(0))
            else:
                y_hat: torch.Tensor = self.model(tensor_img.unsqueeze(0).half().to(self.device))
            y_hat = y_hat[0]
            if isinstance(y_hat, dict):
                for idx, box in enumerate(y_hat['boxes']):
                    if y_hat['scores'][idx] < self.score_threshold:
                        continue
                    x_scale = img_size[1] / self.size
                    y_scale = img_size[0] / self.size
                    xmin_glob, ymin_glob, xmax_glob, ymax_glob = int(box[0] * x_scale) - self.offset, int(box[1] * y_scale) - self.offset, int(box[2] * x_scale) + self.offset, int(box[3] * y_scale) + self.offset
                    xmin, ymin, xmax, ymax = int(box[0]) - self.offset, int(box[1]) - self.offset, int(box[2]) + self.offset, int(box[3]) + self.offset
                    mask = np.asarray(v2.ToPILImage()(y_hat['masks'][idx].detach().cpu()))
                    mask_area = mask[ymin:ymax, xmin:xmax]
                    _, mask_th = cv2.threshold(mask_area, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                    try:
                        contours_area, _ = cv2.findContours(mask_th, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
                        contour = [(int((p[0][1] - self.offset) * y_scale) + self.offset, int((p[0][0] - self.offset) * x_scale) + self.offset) for p in contours_area[0]]
                        # print(contour)
                        boxes.append(BoundBox(xmin=xmin_glob, ymin=ymin_glob,
                                              xmax=xmax_glob, ymax=ymax_glob, contour=contour, confidence=float(y_hat['scores'][idx].detach().cpu())))
                    except IndexError:
                        continue
                return boxes
            else:
                print('Return from network is in wrong format')
        else:
            print('Image format is not numpy, skipping')


class ADPKDSegmenter(QObject):

    def __init__(self, checkpoint, size=384):
        super().__init__()
        self.size = size
        self.device = 'cpu'
        if torch.cuda.is_available():
            self.device = 'cuda'
        elif torch.backends.mps.is_available():
            self.device = 'mps'
        print(f'Segmentation using {self.device} as computing device')
        print(checkpoint)
        self.model = ADPKDSegmentationModel.load_from_checkpoint(checkpoint)
        if self.device == 'cpu':
            self.model = self.model.eval()
        else:
            self.model = self.model.eval().half().to(self.device)
        self.transform = v2.Compose([
            v2.ToPILImage(),
            v2.Resize((self.size, self.size)),
            v2.ToTensor()
        ])

    def predict(self, img: np.ndarray, img_size=None):
        if img_size is None:
            height, width = img.shape[:2]
        else:
            height, width = img_size
        x_scale, y_scale = width / self.size, height / self.size
        if isinstance(img, np.ndarray):
            tensor_img: torch.Tensor = self.transform(img)
            if self.device == 'cpu':
                y_hat: torch.Tensor = self.model(tensor_img.unsqueeze(0))
            else:
                y_hat: torch.Tensor = self.model(tensor_img.unsqueeze(0).half().to(self.device))
            y_hat = y_hat.squeeze(0)
            if self.device == 'cpu':
                mask = np.asarray(v2.ToPILImage()(y_hat)).astype(np.uint8)
            else:
                mask = np.asarray(v2.ToPILImage()(y_hat.detach().cpu())).astype(np.uint8)
            _, mask_th = cv2.threshold(mask, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            try:
                contours_area, _ = cv2.findContours(mask_th, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
                contour = [(int(p[0][1] * y_scale), int(p[0][0] * x_scale)) for p in contours_area[0]]
                return contour
            except IndexError:
                return []
