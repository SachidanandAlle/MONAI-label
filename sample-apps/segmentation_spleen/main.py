import logging
import os

from lib import MyInfer, MyTrain
from lib.activelearning import MyStrategy, Tta
from monai.apps import load_from_mmar

from monailabel.interfaces import MONAILabelApp
from monailabel.utils.activelearning import Random
from monailabel.utils.scoring.tta_scoring import TtaScoring

logger = logging.getLogger(__name__)


class MyApp(MONAILabelApp):
    def __init__(self, app_dir, studies):
        self.model_dir = os.path.join(app_dir, "model")
        self.final_model = os.path.join(self.model_dir, "model.pt")

        self.mmar = "clara_pt_spleen_ct_segmentation_1"

        super().__init__(app_dir, studies, os.path.join(self.model_dir, "train_stats.json"))

    def init_infers(self):
        infers = {
            "segmentation_spleen": MyInfer(self.final_model, load_from_mmar(self.mmar, self.model_dir)),
        }

        # Simple way to Add deepgrow 2D+3D models for infer tasks
        infers.update(self.deepgrow_infer_tasks(self.model_dir))
        return infers

    def init_strategies(self):
        return {
            "random": Random(),
            "first": MyStrategy(),
            "Tta": Tta(),
        }

    def init_scoring_methods(self):
        return {
            "tta_scoring": TtaScoring(),
        }

    def train(self, request):
        logger.info(f"Training request: {request}")

        output_dir = os.path.join(self.model_dir, request.get("name", "model_01"))

        # App Owner can decide which checkpoint to load (from existing output folder or from base checkpoint)
        load_path = os.path.join(output_dir, "model.pt")
        if not os.path.exists(load_path) and request.get("pretrained", True):
            load_path = None
            network = load_from_mmar(self.mmar, self.model_dir)
        else:
            network = load_from_mmar(self.mmar, self.model_dir, pretrained=False)

        # Datalist for train/validation
        train_d, val_d = self.partition_datalist(self.datastore().datalist(), request.get("val_split", 0.2))

        task = MyTrain(
            output_dir=output_dir,
            train_datalist=train_d,
            val_datalist=val_d,
            network=network,
            load_path=load_path,
            publish_path=self.final_model,
            stats_path=self.train_stats_path,
            device=request.get("device", "cuda"),
            lr=request.get("lr", 0.0001),
            val_split=request.get("val_split", 0.2),
            max_epochs=request.get("epochs", 1),
            amp=request.get("amp", True),
            train_batch_size=request.get("train_batch_size", 1),
            val_batch_size=request.get("val_batch_size", 1),
        )
        return task()


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s.%(msecs)03d][%(levelname)5s](%(name)s) - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    app_dir_path = os.path.normpath("/home/adp20local/Documents/MONAILabel/sample-apps/deepedit_spleen")
    studies_path = os.path.normpath("/home/adp20local/Documents/Datasets/monailabel_datasets/spleen/train_small")
    al_app = MyApp(app_dir=app_dir_path, studies=studies_path)
    request = {}
    request["val_batch_size"] = 1
    request["epochs"] = 1
    request["strategy"] = "Tta"
    request["method"] = "tta_scoring"
    al_app.scoring(request)
    al_app.next_sample(request=request)
    return None


if __name__ == "__main__":
    main()
