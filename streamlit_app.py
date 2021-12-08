import streamlit as st
from streamlit import caching
import pandas as pd
import itertools
import logging
from zipfile import ZipFile

# from streamlit.elements.utils import last_index_for_melted_dataframes


def main():
    st.set_page_config(layout="wide")
    st.title("MLprep cellgo automation sheet construction app")
    option = st.selectbox(
        "Input Format",
        (
            "",
            "Input: Manual cellgo construction sheet",
            "Input: Combinatorial cellgo construction sheet",
        ),
    )
    if option == "Input: Combinatorial cellgo construction sheet":
        st.sidebar.subheader(
            "This app is for creating the sheets used by the MLprep to carry"
            " out transfers from a source to target plate to create"
            " Cellgorithms.     It takes two input CSV files (not xlsx!). The"
            " first is the key file it is 3 columns. It lists the targets in"
            " column 1 (usually a gene),  the concomitant proguide id in column"
            " 2, and the step it is used at in column 3  The second file the"
            " source sheet is 2 columns it has the proguide id in the first"
            " columnand the location, i.e. the well in the source plate in the"
            " second column The program the then creates all permutations of"
            " one proguide per step based on all the proguides in the key file "
            " It then builds the MLprep automation sheet to build those"
            " cellgorithms using the mapping in the source file. Additionally"
            " information on the limiting proguides  and other metrics are in a"
            " separate file included upon download of result."
        )

        col1, col2, col3 = st.columns(3)
        with col1:
            st.image(
                "data/mlprep.png",
                caption="MLprep robot",
            )
        example_key = pd.read_csv("data/key.csv", header=0, quoting=3)
        example_source = pd.read_csv(
            "data/source_sheet.csv", header=0, quoting=3
        )
        with col2:
            st.write(example_key)
            st.caption(
                "This is an example key file csv. The first column is the gene"
                " target name, the second is the proguide id and the third is"
                " what step you would like it used at."
            )
        with col3:
            st.write(example_source)
            st.caption(
                "This is an example source sheet csv. This lists the proguide"
                " ids in the first column and the well in source plate in the"
                " second."
            )
        uploaded_key = st.file_uploader(
            "Choose a key file",
            type=["csv"],
        )
        uploaded_source = st.file_uploader("Choose a source file", type=["csv"])
        with open("cellgo_stats.txt", "w"):
            pass
        logging.basicConfig(
            filename="cellgo_stats.txt",
            filemode="w",
            format="%(message)s",
            datefmt="%H:%M:%S",
            level=logging.INFO,
            force=True,
        )
        if (uploaded_key is not None) & (uploaded_source is not None):
            key = pd.read_csv(uploaded_key, header=0, quoting=3)
            source = pd.read_csv(uploaded_source, header=0, quoting=3)
            col4, col5 = st.columns(2)
            with col4:
                st.write(key)
                st.caption("Your key file")
            with col5:
                st.write(source)
                st.caption("Your source file")
            st.write(key)
            st.write(source)
            # number of unique steps
            num_steps = len(set(key.step))
            num_targets = len(set(key.target))
            num_pgps = len(set(key.pgp))
            g = key.groupby(by="step")
            # list of lists with each sublist all the pgps that can possibly be used in that step
            pgp_steps = [list(group[1].pgp) for group in g]
            target_steps = [list(group[1].target) for group in g]
            # inner product
            pgp_combos = [p for p in itertools.product(*pgp_steps)]
            pgp_flat_combos = [
                proguide for sublist in pgp_combos for proguide in sublist
            ]
            target_combos = [p for p in itertools.product(*target_steps)]
            target_flat_combos = [
                target for sublist in target_combos for target in sublist
            ]
            num_cellgos = len(pgp_combos)
            logging.info(f"Number of unique cellgorithm steps is {num_steps}")
            logging.info(f"Number of proguides used is {num_pgps}")
            logging.info(f"Number of unique targets is {num_targets}")
            logging.info(
                f"Number of unique cellgos|unique TargetWells is {num_cellgos}"
            )
            logging.info(
                "Total number of robotic transfers from source plate is"
                f" {num_cellgos*num_steps}"
            )

            # make skeletong of automation sheet
            df = pd.DataFrame(
                columns=[
                    "SourceSite",
                    "SourceWell",
                    "TargetSite",
                    "TargetWell",
                    "pgp",
                    "target",
                ]
            )
            # make 96 well representation as a list of 96 elements
            wells = [
                f"{letter}{i}"
                for letter in ["A", "B", "C", "D", "E", "F"]
                for i in range(1, 13)
            ]
            # as many wells in target plate as number of cellgos, for each well the number of rows is determined by the number
            # of steps as that is how many transfers have to occur
            well_rows = [
                x
                for item in wells[0:num_cellgos]
                for x in itertools.repeat(item, num_steps)
            ]
            df["TargetWell"] = well_rows
            df["TargetSite"] = 3
            df["SourceSite"] = 1
            df["pgp"] = pgp_flat_combos
            df["target"] = target_flat_combos
            idx = (
                source.reset_index()
                .set_index("pgp")
                .loc[df.pgp, "index"]
                .values.tolist()
            )
            df["SourceWell"] = source.well[idx].tolist()
            df.to_csv("combo_output.csv", sep=",", index=False, quoting=None)
            st.write(df)
            st.subheader("Output automation sheet")
            pgp_table = df.pgp.value_counts()
            pgp_max = pgp_table.max()
            pgp_min = pgp_table.min()
            max_pgp_list = pgp_table[pgp_table == pgp_max].index.tolist()
            min_pgp_list = pgp_table[pgp_table == pgp_min].index.tolist()

            logging.info(
                f"{max_pgp_list} proguide(s) use the most material. Each"
                f" proguide(s) requires {pgp_max} transfers and"
                f" {4  * pgp_max} ul minimum in the source plate (@"
                " 4ul per transfer)"
            )
            logging.info(
                f"{min_pgp_list} proguide(s) use the least material require"
                f" {pgp_min} transfers and {4*pgp_min} ul"
                " minimum in the source plate"
            )
            zipobj = ZipFile("combo_cellgo.zip", "w")
            zipobj.write("combo_output.csv")
            zipobj.write("cellgo_stats.txt")
            zipobj.close()
            with open("combo_cellgo.zip", "rb") as myzip:
                st.download_button(
                    label="Press to download MLprep automation sheet",
                    data=myzip,
                    file_name="combo_cellgo.zip",
                    mime="application/zip",
                    key="download-automation-sheet",
                )

    if option == "Input: Manual cellgo construction sheet":
        st.sidebar.subheader(
            "This app is for creating the sheets used by the MLprep to carry"
            " out transfers from a source to target plate to create"
            " cellgorithms. It takes two input files (neither is an xlsx!). The"
            " key file is a tab separated text file that has one cellgorithm"
            " per row where each column is a different step. Each element can"
            " have one or more proguide ids representing the proguides"
            " activated at that step( column) in that cellgorithm (row)."
            " Multiple proguides at a step in a cellgorithm can be entered"
            " separated by commas. source file that has the target name/gene"
            " name, the proguide id , well location in the source plate, and"
            " another  It then builds the MLprep automation sheet. Additionally"
            " information on the limiting proguides and other metrics is"
            " included in a separate .txt"
        )
        col1, col2, col3 = st.columns([1, 2, 1])
        with col1:
            st.image(
                "data/mlprep.png",
                caption="MLprep robot",
            )
        example_key = pd.read_csv(
            "data/manual_key_example.txt",
            sep="\t",
            header=0,
            quoting=3,
            keep_default_na=False,
        )
        example_source = pd.read_csv(
            "data/source_sheet2.csv", header=0, quoting=3
        )
        with col2:
            st.write(example_key)
            st.caption(
                "This is an example key file. It is a TAB separated text file"
                " (not xlsx!). Each row contains one cellgorithm, each column"
                " corresponds to a single step. Each element in the matrix has"
                " the proguide id's that are activated at that step (column) in"
                " that specifc cellgorithm (row), you can put more than one pgp"
                " id in a element by using commas. You can have cellgorithms of"
                " different lengths.See the example key file."
            )
        with col3:
            st.write(example_source)
            st.caption(
                "This is an example source sheet CSV file. This lists the"
                " target name (gene)  in the first column, the proguide id in"
                " the second, and the well in source plate in the third."
            )
        uploaded_key = st.file_uploader(
            "Choose a key file",
            type=["txt"],
        )
        uploaded_source = st.file_uploader("Choose a source file", type=["csv"])
        if (uploaded_key is not None) & (uploaded_source is not None):
            key = pd.read_csv(
                uploaded_key,
                header=0,
                sep="\t",
                quoting=3,
                keep_default_na=False,
            )
            source = pd.read_csv(uploaded_source, header=0, quoting=3)
            col4, col5 = st.columns(2)
            with col4:
                st.write(key)
                st.caption("Your key file")
            with col5:
                st.write(source)
                st.caption("Your source file")
            key = key.applymap(lambda row: row.replace('"', ""))
            key = key.applymap(lambda row: row.replace(" ", ""))
            pgp_combos_pre = key.values.tolist()
            # remove empty elements i.e. if a row has less steps than other rows
            pgp_combos_pre = [
                [element for element in sublist if element != ""]
                for sublist in pgp_combos_pre
            ]
            pgp_combos = [tuple(x) for x in pgp_combos_pre]
            pgp_flat_combos = [
                proguide for sublist in pgp_combos for proguide in sublist
            ]
            pgp_flat_combos_split = [
                proguide
                for sublist in pgp_flat_combos
                for proguide in sublist.split(",")
            ]
            # target_combos = [tuple(x) for x in source.values.tolist()]
            # target_flat_combos = [
            #    target for sublist in target_combos for target in sublist
            # ]
            max_steps = len((key.columns))
            num_pgps = len(set(pgp_flat_combos_split))
            num_cellgos = len(key.index)
            pgp_combos_fixed = []
            for element in pgp_combos_pre:
                the_list = [
                    map(lambda x: x.strip(), item.split(","))
                    for item in element
                ]
                my_tuple = tuple(
                    item for sub_list in the_list for item in sub_list
                )
                pgp_combos_fixed.append(my_tuple)
            pgp_combos_fixed_lengths = [len(item) for item in pgp_combos_fixed]
            wells = [
                f"{letter}{i}"
                for letter in ["A", "B", "C", "D", "E", "F"]
                for i in range(1, 13)
            ]
            well_rows = list(
                itertools.chain.from_iterable(
                    [
                        itertools.repeat(item, count)
                        for item, count in zip(
                            wells[0:num_cellgos], pgp_combos_fixed_lengths
                        )
                    ]
                )
            )
            df = pd.DataFrame(
                columns=[
                    "SourceSite",
                    "SourceWell",
                    "TargetSite",
                    "TargetWell",
                    "pgp",
                ]
            )
            df["TargetWell"] = well_rows
            df["TargetSite"] = 3
            df["SourceSite"] = 1
            df["pgp"] = pgp_flat_combos_split
            idx = (
                source.reset_index()
                .set_index("pgp")
                .loc[df.pgp, "index"]
                .values.tolist()
            )
            df["SourceWell"] = source.well[idx].tolist()
            df = pd.merge(
                left=df, right=source[["pgp", "target"]], how="left", on="pgp"
            )
            df.to_csv("manual_output.csv", sep=",", index=False, quoting=None)
            st.write(df)
            st.subheader("Output automation sheet")
            pgp_table = df.pgp.value_counts()
            pgp_max = pgp_table.max()
            pgp_min = pgp_table.min()
            max_pgp_list = pgp_table[pgp_table == pgp_max].index.tolist()
            min_pgp_list = pgp_table[pgp_table == pgp_min].index.tolist()
            num_targets = len(set(df.target))
            pipets_needed = len(df.index)
            with open("cellgo_stats.txt", "w"):
                pass
            logging.basicConfig(
                filename="cellgo_stats.txt",
                filemode="w",
                format="%(message)s",
                datefmt="%H:%M:%S",
                level=logging.INFO,
                force=True,
            )
            logging.info(
                f"Max number of unique cellgorithm steps is {max_steps}"
            )
            logging.info(f"Number of proguides used is {num_pgps}")
            logging.info(f"Number of unique targets is {num_targets}")
            logging.info(
                f"Number of unique cellgos|unique TargetWells is {num_cellgos}"
            )
            logging.info(
                "Total number of pipets needed/robotic transfers is"
                f" {pipets_needed}"
            )
            logging.info(
                f"{max_pgp_list} proguide(s) use the most material. Each"
                f" proguide(s) requires {pgp_max} transfers and"
                f" {4  * pgp_max} ul minimum in the source plate (@ 4ul per"
                " transfer)"
            )
            logging.info(
                f"{min_pgp_list} proguide(s) use the least material require"
                f" {pgp_min} transfers and {4 * pgp_min} ul minimum in the"
                " source plate"
            )
            zipobj = ZipFile("manual_cellgo.zip", "w")
            zipobj.write("manual_output.csv")
            zipobj.write("cellgo_stats.txt")
            zipobj.close()
            with open("manual_cellgo.zip", "rb") as myzip:
                st.download_button(
                    label="Press to download MLprep automation sheet",
                    data=myzip,
                    file_name="manual_cellgo.zip",
                    mime="application/zip",
                    key="download-automation-sheet",
                )


if __name__ == "__main__":
    if st._is_running_with_streamlit:
        main()
