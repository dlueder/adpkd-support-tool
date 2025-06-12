import torch
import torchvision
import lightning as L
from torchvision.models.detection.backbone_utils import _resnet_fpn_extractor, _validate_trainable_layers
from torchvision.models.detection._utils import overwrite_eps
from torchvision.models.detection.mask_rcnn import MaskRCNN
import segmentation_models_pytorch as smp
# from segmentation_models_pytorch.losses import DiceLoss
# from segmentation_models_pytorch.utils.metrics import IoU


class ADPKDModel(L.LightningModule):
    def __init__(self):
        super().__init__()
        weights_backbone = torchvision.models.ResNet50_Weights.IMAGENET1K_V1
        trainable_backbone_layers = _validate_trainable_layers(False, 5, 5, 3)
        backbone = torchvision.models.resnet.resnet50(weights=weights_backbone, norm_layer=None, progress=True)  # if normalization is None it will be BatchNorm2D
        backbone = _resnet_fpn_extractor(backbone, trainable_backbone_layers)
        self.model = MaskRCNN(backbone, num_classes=2, rpn_score_thresh=0.80)  # background and only one class
        overwrite_eps(self.model, 0.0)

    def forward(self, x):
        return self.model(x)

    def training_step(self, batch, batch_idx):
        del batch_idx
        X, y = batch
        loss_dict = self.model(X, y)
        print(loss_dict)
        for k, v in loss_dict.items():
            self.log(k, float(v))
        loss = sum(loss for loss in loss_dict.values())
        self.log("train_loss", float(loss))
        return loss

    def configure_optimizers(self):
        return torch.optim.SGD(self.model.parameters(), lr=0.002, momentum=0.9, weight_decay=1e-4)  # lower lr as in reference in order to avoid NaN gradients


class ADPKDSegmentationModel(L.LightningModule):
    def __init__(self):
        super().__init__()
        self.model = smp.Unet(encoder_name='timm-resnest26d', encoder_weights='imagenet', in_channels=3, classes=1, activation='sigmoid')
        # self.loss = DiceLoss(mode='binary')
        # self.metrics = [IoU(threshold=0.90)]

    def forward(self, x):
        return self.model(x)

    def training_step(self, batch, batch_idx):
        del batch_idx
        X, y = batch
        pred = self.model(X)
        loss = self.loss(pred, y)
        self.log("train_loss", float(loss))
        return loss

    def configure_optimizers(self):
        return torch.optim.Adam(self.model.parameters(), lr=0.0001)
