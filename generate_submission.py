import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from PIL import Image
from sklearn.model_selection import train_test_split
from skorch import NeuralNet
from torchvision.transforms import Compose, RandomCrop, Resize, ToPILImage, ToTensor

from dataset import UsgDataset
from model import PretrainedModel
from train import fscore_as_metric, get_timestamp

torch.multiprocessing.set_sharing_strategy('file_system')


def generate_submission(data_folder: str, weights_path: str):
    weights_path = Path(weights_path)
    assert weights_path.exists()

    data_paths = list((Path(data_folder) / "train").rglob("radial_polar_area.png"))

    classes = [int(path.parent.parent.name) for path in data_paths]
    train_paths, valid_paths = train_test_split(data_paths, test_size=0.3, stratify=classes)

    transforms = Compose([
        ToPILImage(),
        RandomCrop(128, pad_if_needed=True),
        Resize(128, interpolation=Image.LANCZOS),
        ToTensor()
    ])

    train_dataset = UsgDataset(train_paths, True, transforms=transforms)
    valid_dataset = UsgDataset(valid_paths, True, transforms=transforms)

    net = NeuralNet(
        PretrainedModel,
        criterion=nn.CrossEntropyLoss,
        iterator_valid__shuffle=False,
        iterator_valid__num_workers=2,
        iterator_valid__batch_size=1,
        device="cuda",
    )
    net.initialize()
    net.load_params(f_params=weights_path.as_posix())

    test_data_paths = list((Path(data_folder) / "test").rglob("radial_polar_area.png"))
    test_dataset = UsgDataset(test_data_paths, is_train_or_valid=False, transforms=Compose([
        ToTensor()
    ]))

    valid_predictions = net.predict(valid_dataset)
    valid_trues = np.asarray([int(path.parent.parent.name) for path in valid_paths])
    val_acc = fscore_as_metric(valid_predictions, valid_trues)

    predictions = net.predict(test_dataset)

    ids = [path.parent.name for path in test_data_paths]
    classes = np.argmax(predictions, axis=1)
    frame = pd.DataFrame(data={"id": ids, "label": classes})
    frame["id"] = frame["id"].astype(np.int32)
    frame = frame.sort_values(by=["id"])
    frame.to_csv(f"submissions/{get_timestamp()}_{'%.4f' % val_acc}_submission.csv", index=False)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "data_folder",
        help="Folder with 'train' and 'test' folders prepared for the competition."
    )
    parser.add_argument(
        "model_folder",
        help="Folder with model to use for prediction."
    )

    args = parser.parse_args()
    generate_submission(args.data_folder, args.model_folder)


if __name__ == '__main__':
    main()
