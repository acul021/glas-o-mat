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
        self.__containers = None
        self.__construction_types = None
        self.__aggregated = None

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

    @property
    def construction_types(self) -> pd.DataFrame:
        if self.__construction_types is None:
            self.__load_construction_types()
        return self.__construction_types

    @property
    def aggregated(self) -> pd.DataFrame:
        if self.__aggregated is None:
            self.__load_aggregated()
        return self.__aggregated

    @property
    def containers(self) -> pd.DataFrame:
        if self.__containers is None:
            self.__load_containers()
        return self.__containers

    def preload(self):
        self.__load_locations()
        self.__load_activities()
        self.__load_containers()
        self.__load_construction_types()
        self.__load_aggregated()

    def __load_aggregated(self):
        self.__aggregated = pd.merge(self.activities, self.containers, on='CONTAINER_ID',
                                     how='left', validate='many_to_one')
        self.__aggregated.loc[
            self.__aggregated['CONSTRUCTION_TYPE_ID'].isnan(), 'CONSTRUCTION_TYPE_ID'] = 1
        self.__aggregated = pd.merge(self.__aggregated, self.construction_types,
                                     on='CONSTRUCTION_TYPE_ID', how='inner', validate='many_to_one')
        self.__aggregated['LEVEL'] = self.__aggregated['SLIDER_LEVEL'] * self.__aggregated[
            'VOLUME'] / 100

    def __load_containers(self):
        self.__containers = pd.read_csv(f'{self.path}/Containers.csv')

    def __load_locations(self):
        self.__locations = pd.read_csv(f'{self.path}/Locations.csv')

    def __load_construction_types(self):
        self.__construction_types = pd.read_csv(f'{self.path}/ConstructionTypes.csv')

    def __load_activities(self):
        self.__activities = pd.read_csv(f'{self.path}/ContainerActivities.csv')

        # type conversion
        self.__activities['RECORDED_AT'] = pd.to_datetime(self.__activities['RECORDED_AT'])
        self.__activities['PHONE_ID'] = self.__activities['PHONE_ID'].astype(str)

        self.__activities.sort_values(['RECORDED_AT', 'TRANSACTION_ID'], inplace=True)

        # drop test phone
        self.__activities = self.__activities[~self.__activities['PHONE_ID'].str.startswith('TKQ1')]

        # calc location id from container id and material type
        self.__activities['LOCATION_ID'] = self.__activities['CONTAINER_ID'].astype(str).str.slice(
            0, -4).astype(np.uint64)
        self.__activities['MATERIAL_ID'] = self.__activities['CONTAINER_ID'].astype(str).str.slice(
            -4, -2).astype(np.uint64)
        self.__activities['DATE'] = self.__activities['RECORDED_AT'].dt.date.astype(str)

        # calc intervals
        self.__calc_intervals()

        # cleanup - remove duplicates
        self.__activities.dropna(subset=['INTERVAL'], inplace=True)
        self.__activities['IS_EMPTIED'] = \
            self.__activities.groupby(['CONTAINER_ID', 'DATE'])['IS_EMPTIED'].cummax()
        self.__activities.drop_duplicates(subset=['CONTAINER_ID', 'DATE'], inplace=True,
                                          keep='last')

        # calc intervals
        self.__calc_intervals()

        self.__activities.reset_index(drop=True, inplace=True)

    def __calc_intervals(self):
        self.__activities['INTERVAL'] = self.__activities. \
            groupby('CONTAINER_ID')['RECORDED_AT'].diff()
        self.__activities['EMPTIED_INTERVAL'] = \
            self.__activities[self.__activities['IS_EMPTIED'] == 1]. \
                groupby('CONTAINER_ID')['RECORDED_AT'].diff()



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
