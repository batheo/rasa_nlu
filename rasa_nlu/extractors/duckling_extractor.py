from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import os
import io
import json
import typing
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Text

from builtins import str

from rasa_nlu.config import RasaNLUConfig
from rasa_nlu.extractors import EntityExtractor
from rasa_nlu.model import Metadata
from inspect import getmembers

from rasa_nlu.training_data import Message

if typing.TYPE_CHECKING:
    from duckling import DucklingWrapper


class DucklingExtractor(EntityExtractor):
    """Adds entity normalization by analyzing found entities and transforming them into regular formats."""

    name = "ner_duckling"

    provides = ["entities"]

    output_provides = ["entities"]

    @staticmethod
    def available_dimensions():
        from duckling.dim import Dim
        return [m[1] for m in getmembers(Dim) if not m[0].startswith("__") and not m[0].endswith("__")]

    def __init__(self, duckling, dimensions=None):
        # type: (DucklingWrapper, Optional[List[Text]]) -> None

        self.dimensions = dimensions if dimensions is not None else self.available_dimensions()
        self.duckling = duckling

    @classmethod
    def required_packages(cls):
        # type: () -> List[Text]
        return ["duckling"]

    @classmethod
    def _create_duckling_wrapper(cls, language):
        from duckling import DucklingWrapper

        try:
            return DucklingWrapper(language=language)  # languages in duckling are eg "de$core"
        except ValueError as e:     # pragma: no cover
            raise Exception("Duckling error. {}".format(e))

    @classmethod
    def create(cls, config):
        # type: (RasaNLUConfig) -> DucklingExtractor

        dims = config["duckling_dimensions"]
        if dims:
            unknown_dimensions = [dim for dim in dims if dim not in cls.available_dimensions()]
            if len(unknown_dimensions) > 0:
                raise ValueError("Invalid duckling dimension. Got '{}'. Allowed: {}".format(
                    ", ".join(unknown_dimensions), ", ".join(cls.available_dimensions())))

        return DucklingExtractor(cls._create_duckling_wrapper(config["language"]), dims)

    @classmethod
    def cache_key(cls, model_metadata):
        # type: (Metadata) -> Text

        return cls.name + "-" + model_metadata.language

    def process(self, message, **kwargs):
        # type: (Message, **Any) -> None

        extracted = []
        if self.duckling is not None:
            matches = self.duckling.parse(message.text)
            relevant_matches = [match for match in matches if match["dim"] in self.dimensions]
            for match in relevant_matches:
                entity = {"start": match["start"],
                          "end": match["end"],
                          "text": match["text"],
                          "value": match["value"]["value"],
                          "entity": match["dim"]}

                extracted.append(entity)

        extracted = self.add_extractor_name(extracted)
        message.set("entities", message.get("entities", []).extend(extracted))

    def persist(self, model_dir):
        # type: (Text) -> Dict[Text, Any]

        file_name = self.name+".json"
        full_name = os.path.join(model_dir, file_name)
        with io.open(full_name, 'w') as f:
            f.write(str(json.dumps({"dimensions": self.dimensions})))
        return {"ner_duckling_persisted": file_name}

    @classmethod
    def load(cls, model_dir, model_metadata, **kwargs):
        # type: (Text, Metadata, **Any) -> DucklingExtractor

        persisted = os.path.join(model_dir, model_metadata.get("ner_duckling_persisted"))
        if os.path.isfile(persisted):
            with io.open(persisted, encoding='utf-8') as f:
                persisted_data = json.loads(f.read())
                return DucklingExtractor(cls._create_duckling_wrapper(model_metadata.get("language")),
                                         persisted_data["dimensions"])
        return DucklingExtractor(cls._create_duckling_wrapper(model_metadata.get("language")))
