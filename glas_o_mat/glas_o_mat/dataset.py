import pandas as pd
import numpy as np

class DataframeWrapper(pd.DataFrame):
    pass


class Dataset:

    def __init__(self, path: str):
        super().__init__()
        self.__path = path
        self.__activities = None
        self.__locations = None

    @property
    def path(self) -> str:
        return self.__path

    @property
    def activities(self) -> pd.DataFrame:
        if self.__activities is None:
            self.__load_activities()
        return self.__activities

    @property
    def locations(self) -> pd.DataFrame:
        if self.__locations is None:
            self.__load_locations()
        return self.__locations

    def preload(self):
        self.__load_locations()
        self.__load_activities()

    def __load_locations(self):
        self.__locations = pd.read_csv(f'{self.path}/Locations.csv')

    def __load_activities(self):
        self.__activities = pd.read_csv(f'{self.path}/ContainerActivities.csv')

        # type conversion
        self.__activities['RECORDED_AT'] = pd.to_datetime(self.__activities['RECORDED_AT'])
        self.__activities['PHONE_ID'] = self.__activities['PHONE_ID'].astype(str)

        self.__activities.sort_values(['RECORDED_AT', 'TRANSACTION_ID'], inplace=True)

        # drop test phone
        self.__activities = self.__activities[~self.__activities['PHONE_ID'].str.startswith('TKQ1')]

        # calc location id from container id and material type
        self.__activities['LOCATION_ID'] = self.__activities['CONTAINER_ID'].astype(str).str.slice(0, -4).astype(np.uint64)
        self.__activities['MATERIAL_ID'] = self.__activities['CONTAINER_ID'].astype(str).str.slice(-4, -2).astype(np.uint64)
        self.__activities['DATE'] = self.__activities['RECORDED_AT'].dt.date.astype(str)
        # calc intervals
        self.__activities['INTERVAL'] = self.__activities.groupby('CONTAINER_ID')['RECORDED_AT'].diff().dt.total_seconds()

        self.__activities.reset_index(drop=True, inplace=True)


def create_dataset() -> Dataset:
    """
    Create a new dataset object.
    """
    return Dataset('../data')


def load_data() -> Dataset:
    """
    Load the dataset from the data folder. This function preloads the data into memory.
    """
    dataset = create_dataset()
    dataset.preload()
    return dataset
