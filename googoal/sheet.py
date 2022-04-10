import warnings
from collections import defaultdict

import numpy as np
import pandas as pd

import gspread

from .config import *
from .log import Logger
from .drive import Drive, Resource
from .util import iframe_url

log = Logger(
    name=__name__,
    level=config["logging"]["level"],
    filename=config["logging"]["filename"]
)


MIME = "application/vnd.google-apps.spreadsheet"

class Sheet():
    """
    Class for interchanging information between google spreadsheets and pandas data frames. The class manages a spreadsheet.

    :param worksheet_name: the worksheet in the spreadsheet to work with (default None which causes Sheet1 to be the name)
    :param title: the title of the spreadsheet (used if the spreadsheet is created for the first time)
    :param col_indent: the column indent to use in the spreadsheet.
    :type col_indent: int
    :param drive: the google drive client to use (default is None which performs a programmatic login)
    :param gs_client: the google spread sheet client login (default is none which causes a new client login)
    :param header: number of header rows in the document.
    :type header: int
    :param na_values: additional list containing entry types that are to be considered to be missing data (default is empty list).
    :type na_values: list
    :param dtype: Type name or dict of column -> type Data type for data or columns. E.g. {'a': np.float64, 'b': np.int32}
    :type dtype: dictonary
    :param raw_values: whether to read values rather than the formulae in the spreadsheet (default is False).
    :type raw_values: bool
    """

    def __init__(
            self,
            resource=None,
            gs_client=None,
            name=None,
            worksheet_name=None,
            index_field=None,
            col_indent=0,
            na_values=["nan"],
            dtype={},
            raw_values=False,
            header=1,
    ):
        source = "ODS Gdata Bot"
        scope = ["https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        if name is None:
            self.name = "Google Sheet"
        else:
            self.name = name
        log.info(f"Creating new spreadsheet {self.name}.")
        self.raw_values = raw_values
        self.header = header
        self.index_field = None
        if type(na_values) is str:
            na_values = [na_values]
        self.na_values = na_values
        self.dtype = dtype

        if resource is None:
            drive = Drive(scope=scope)
            self.resource = Resource(
                drive=drive, name=self.name, mime_type=MIME
            )
        else:
            if "https://www.googleapis.com/auth/spreadsheets" not in resource.drive.scope:
                drive = Drive(scope=scope)
                resource.update_drive(drive)
            self.resource = resource

        # Get a Google sheets client
        if gs_client is None:
            self.gs_client = gspread.authorize(self.resource.drive.credentials)
        else:
            self.gs_client = gs_client

        self.sheet = self.gs_client.open_by_key(self.id)

        if worksheet_name is None:
            self.worksheet = self.sheet.worksheets()[0]
        else:
            self.worksheet = self.sheet.worksheet(title=worksheet_name)
        self.col_indent = col_indent
        

    #############################################################################
    # Place methods here that are really associated with individual worksheets. #
    #############################################################################

    def change_sheet_name(self, title):
        """Change the title of the current worksheet to title."""
        raise NotImplementedError
        raise ValueError(
            "Can't find worksheet "
            + self.worksheet_name
            + " to change the name in Google spreadsheet "
            + self.url
        )

    def set_sheet_focus(self, worksheet_name):
        """Set the current worksheet to the given name. If the name doesn't exist then create the sheet using sheet.add_worksheet()"""
        self.worksheets = self.sheet.worksheets()
        # if the worksheet is set to None default to first sheet, warn if it's name is not "Sheet1".
        names = [worksheet.title for worksheet in self.worksheets]
        if worksheet_name is None:
            self.worksheet_name = self.worksheets[0].title
            if len(self.worksheets) > 1 and self.worksheet_name != "Sheet1":
                print(
                    "Warning, multiple worksheets in this spreadsheet and no title specified. Assuming you are requesting the sheet called '{sheetname}'. To surpress this warning, please specify the sheet name.".format(
                        sheetname=self.worksheet_name
                    )
                )
        else:
            if worksheet_name not in names:
                # create new worksheet here.
                self.sheet.add_worksheet(title=worksheet_name)
                self.worksheet_name = worksheet_name
            else:
                self.worksheet_name = worksheet_name
                # self.worksheet = self.sheet.set_worksheet(self.worksheet_name)
        # Get list of ids from the spreadsheet
        self.worksheet = self.sheet.worksheet(self.worksheet_name)

    def add_sheet(self, worksheet_name, rows=100, cols=10):
        """Add a worksheet. To add and set to the current sheet use set_sheet_focus()."""
        self.sheet.add_worksheet(title=worksheet_name, rows=rows, cols=cols)
        self.worksheets = self.sheet.worksheets()

    def write(self, data_frame, comment=None):
        """
        Write a pandas data frame to a google document. This function will overwrite existing cells, but will not clear them first.

        :param data_frame: the data frame to write.
        :type data_frame: pandas.DataFrame
        :param comment: a comment to make at the top of the document (requres header>1
        :type comment: str
        """
        if comment is not None:
            if self.header == 1:
                raise ValueError("Comment will be overwritten by column headers")
            self.write_comment(comment)

        self.write_headers(data_frame)
        self.write_body(data_frame)

    def augment(self, data_frame, columns, comment=None):
        """
        Augment is a special wrapper function for update that calls it
        with overwrite set to False. Use this command if you only want
        to make changes when the cell in the spreadsheet is empty.
        """
        self.update(data_frame, columns, comment, overwrite=False)

    def update(self, data_frame, columns=None, comment=None, overwrite=True):
        """
        Update a google document with a given data frame. The
        update function assumes that the columns of the data_frame and
        the google document match, and that an index in either the
        google document or the local data_frame identifies one row
        uniquely. If columns is provided as a list then only the
        listed columns are updated.

        **Notes**

        :data_frame : data frame to update the spreadsheet with.
        :type data_frame: pandas.DataFrame
        :param columns: which columns are updated in the spreadsheet (by default all columns are updated)
        :type columns: list
        :param comment: comment to place in the top row of the header (requires header>1)
        :type comment: str
        :rtype: pandas.DataFrame

        .. Note:: Returns the data frame that was found in the spreadsheet.

        """
        if not data_frame.index.is_unique:
            raise ValueError(
                "Index for data_frame is not unique in provided data frame for spreadsheet "
                + self.url
            )
        ss = self.read()
        if not ss.index.is_unique:
            raise ValueError(f"Index in sheet is not unique in Google spreadsheet {self.url}")
        if columns is None:
            columns = ss.columns
        if (
            len(set(ss.columns) - set(data_frame.columns)) > 0
            or len(set(data_frame.columns) - set(ss.columns)) > 0
        ):
            # TODO: Have a lazy option that doesn't mind this mismatch and accounts for it.
            raise ValueError(f"There is a mismatch between columns in online spreadsheet and the data frame we are using to update in the Google spreadsheet {self.url}")

        add_row = []
        remove_row = []
        update_triples = []
        # Compute necessary changes
        for index in data_frame.index:
            if index in ss.index:
                for column in columns:
                    ss_val = ss[column][index]
                    df_val = data_frame[column][index]
                    ty = type(df_val)
                    log.info(f"value is {df_val} type is {ty}")
                    if overwrite:
                        if not ss_val == df_val:
                            update_triples.append((index, column, df_val))
                    else:
                        if (
                                (pd.isnull(ss_val) or ss_val == "")
                                and not
                                (pd.isnull(df_val) or df_val == "")
                        ):
                            update_triples.append((index, column, df_val))

            else:
                add_row.append(index)

        if overwrite:
            for index in ss.index:
                if index not in data_frame.index:
                    remove_row.append(index)

        index_to_add = []
        index_to_rem = []
        swap_list = []

        swap_len = min(len(add_row), len(remove_row))
        row_change = len(add_row) - len(remove_row)

        if row_change > 0:
            index_to_add = add_row[-row_change:]

        if row_change < 0:
            index_to_rem = remove_row[row_change:]

        for add, rem in zip(add_row[:swap_len], remove_row[:swap_len]):
            swap_list.append((add, rem))

        cells = []
        for index, column, val in update_triples:
            cell = self._cell(index, column)
            cell = self._set_cell_val(cell, val)
            cells.append(cell)

        for add, rem in swap_list:
            cells.extend(
                self._overwrite_row(
                    index=rem,
                    new_index=add,
                    data_series=data_frame.loc[add],
                )
            )

        if index_to_rem:
            cells.extend(self._delete_rows(index_to_rem))
        if index_to_add:
            cells.extend(self._add_rows(data_frame.loc[index_to_add]))
            
        self._update_cells(cells)

    def _update_cells(self, cells):
        self.worksheet.update_cells(cells, value_input_option='RAW')

    def _update_cell(self, row, col, val):
        self.worksheet.update_cell(row, col, val)

    def _update_row_lookup(self, index):
        """Update the data series to be used as a look-up to find row associated with each index.
        :param index: the index names in order from the spreadsheet.
        :type index: list"""
        self.row_lookup = pd.Series(
            range(self.header + 1, len(index) + self.header + 1), index=index
        )

    def _update_col_lookup(self, columns):
        """Update the data series to be used as a look-up to find col associated with each column.
        :param column: the column names in order from the spreadsheet.
        :type column: list"""
        self.col_lookup = pd.Series(
            range(self.col_indent + 1, len(columns) + self.col_indent + 1),
            index=columns,
        )

    def _cell(self, index, column):
        """Return the cell of the spreadsheet associated with the given index and column."""
        return self.worksheet.cell(self.row_lookup[index], self.col_lookup[column])

    def _overwrite_row(self, index, new_index, data_series):
        """Overwrite the given row in a spreadsheet with a data series."""
        cells = []
        for column in self.col_lookup.index:
            cell = self._cell(index, column)
            if column in data_series.index:
                val = data_series[column]
            elif column == self.index_field:
                val = new_index
            else:
                val = None
            cell = self._set_cell_val(cell, val)
            cells.append(cell)
        return cells

    def _delete_rows(self, index):
        """
        Delete a row of the spreadsheet.
        :param index: the row number to be deleted.
        :type index: index of pd.DataSeries"""
        if not index:
            return
        if type(index) is str:
            index = [index]
        minind = self.row_lookup[index].min()

        start = gspread.utils.rowcol_to_a1(minind, self.col_lookup.min())
        end = gspread.utils.rowcol_to_a1(
            self.row_lookup.max(), self.col_lookup.max()
        )
        cells = self.worksheet.range(start + ":" + end)

        # download existing values
        data = defaultdict(lambda: defaultdict(str))
        for cell in cells:
            row = data.setdefault(int(cell.row), defaultdict(str))
            row[cell.col] = self._get_cell_val(cell)
        delete_rows = self.row_lookup[index].sort_values(inplace=False)
        # Find the ends of the banks to move up
        end_step = []
        for i, ind in enumerate(delete_rows.index):
            if i > 0:
                end_step.append(self.row_lookup[ind] - i)
        end_step.append(self.row_lookup.max() - len(index))

        # Move up each bank in turn.
        for i, ind in enumerate(delete_rows):
            for cell in cells:
                if (i == 0 and cell.row <= end_step[i]) or (
                    i > 0
                    and cell.row <= end_step[i]
                    and cell.row >= end_step[i - 1]
                ):
                    cell = self._set_cell_val(cell, data[cell.row + 1 + i][cell.col])

        # Delete exposed rows at bottom
        for cell in cells:
            if cell.row > end_step[-1]:
                cell = self._set_cell_val(cell, "")

        # Update the row lookups
        for i, ind in enumerate(delete_rows.index):
            self.row_lookup[self.row_lookup > self.row_lookup[ind]] -= i + 1
            self.row_lookup.drop(ind, inplace=True)

        return cells

    def _rowcol_to_a1(self, row, col):
        return gspread.utils.rowcol_to_a1(row, col)

    def _rowcols_range(self, start, end):
        """Return a group of cells from the given start and end coordinates."""
        begin = self._rowcol_to_a1(*start)
        finish = self._rowcol_to_a1(*end)
        return self.worksheet.range(begin + ":" + finish)

    def _add_rows(self, data_frame):
        """
        Add a row to the spreadsheet.
        :param index: index of the row to be added.
        :type index: str or int (any valid index for a pandas.DataFrame)
        :param data_series: the entries of the row to be added.
        :type data_frame: pandas.DataFrame"""

        if type(data_frame) is pd.core.series.Series:
            data_frame = pd.DataFrame(data_frame).T
        maxind = self.row_lookup.max()
        for i, ind in enumerate(self.row_lookup.index):
            self.row_lookup[ind] = maxind + 1 + i
        cells = self._rowcols_range(
            start = (maxind + 1, self.col_lookup.min()),
            end = (maxind + data_frame.shape[0], self.col_lookup.max())
        )
        for cell in cells:
            if cell.value != "":
                raise ValueError("Overwriting non-empty cell in spreadsheet")
            i = cell.row - maxind - 1
            index = data_frame.index[i]
            j = cell.col - self.col_lookup.min() - 1
            if j < 0:
                val = index
            else:
                column = data_frame.columns[j]
                val = data_frame[column][index]
            cell = self._set_cell_val(cell, val)
        for i, ind in enumerate(data_frame.index):
            self.row_lookup[ind] = maxind + 1 + i
        return cells

    def _get_cell_val(self, cell):
        """Get the cell value"""
        if self.raw_values:
            return cell.input_value
        else:
            return cell.value

    def _standard_types(self, val):
        """Convert any data types to types that gspread should recognise."""
        typ = type(val)
        if pd.isna(val):
            return ''
        elif pd.api.types.is_float_dtype(typ):
            return float(val)
        elif pd.api.types.is_integer_dtype(typ):
            return int(val)
        elif pd.api.types.is_string_dtype(typ):
            return str(val)
        else:
            return val
    def _set_cell_val(self, cell, val):
        """Set the cell value"""
        # gspread doesn't handle writing NaN, replace with empty.
        val = self._standard_types(val)
        if self.raw_values:
            cell.input_value = val
        else:
            cell.value = val
        return cell
    
    def write_comment(self, comment, row=1, col=1):
        """Write a comment in the given cell"""
        self._update_cell(row, col, comment)

    def write_body(self, data_frame, nan_val=""):
        """Write the body of a data frame to a google doc."""
        # query needs to be set large enough to pull down relevant cells of sheet.
        row_number = self.header
        cells = self._rowcols_range(
            start = ((row_number + 1, self.col_indent + 1)),
            end = (row_number + data_frame.shape[0], len(data_frame.columns) + self.col_indent + 1),
        )
        for cell in cells:
            if cell.col == self.col_indent + 1:
                if cell.value != "":
                    raise ValueError(
                        "Non-empty cell be written to in Google sheet."
                    )
                # Write index
                cell = self._set_cell_val(cell, data_frame.index[cell.row - self.header - 1])
            else:
                column = data_frame.columns[cell.col - self.col_indent - 2]
                index = data_frame.index[cell.row - self.header - 1]
                val = data_frame[column][index]
                if type(val) is float:
                    if np.isnan(val):
                        val = nan_val
                cell = self._set_cell_val(cell, val)
        self._update_cells(cells)

    def write_headers(self, data_frame):
        """Write the headers of a data frame to the spreadsheet."""

        index_name = data_frame.index.name
        if index_name == "" or index_name is None:
            index_name = "index"
        headers = [index_name] + list(data_frame.columns)
        cells = self._rowcols_range(
            start=(self.header, self.col_indent + 1),
            end=(self.header, len(data_frame.columns) + self.col_indent + 1)
        )
        # Select a range
        self._update_col_lookup(headers)
        for cell, value in zip(cells, headers):
            if cell.value != "":
                raise ValueError("Error over-writing in non empty sheet")
            cell = self._set_cell_val(cell, value)
        # Update in batch
        return self._update_cells(cells)

    def read_headers(self):

        column_names = self.worksheet.row_values(self.header)[self.col_indent :]
        self._update_col_lookup(column_names)

        if self.index_field is None:
            # Return any column titled index or otherwise the first column
            index_col_num = next(
                (
                    i
                    for i, column in enumerate(column_names)
                    if column == "index" or "Index" or "INDEX"
                ),
                0,
            )
            self.index_field = column_names[index_col_num]
        elif self.index_field not in column_names:
            raise ValueError(
                "Invalid index: "
                + self.index_field
                + " not present in sheet header row "
                + str(self.header)
                + "."
            )
        return column_names

    def read_body(self, use_columns=None):
        """
        Read in the body of a google sheet storing entries. 

        :param use_columns: return a subset of the columns.
        :type use_columns: list
        """
        # Find the index column number.
        if self.index_field in self.col_lookup:
            index_col_num = self.col_lookup[self.index_field]
        else:
            raise ValueError(
                "Column "
                + self.index_field
                + " suggested for index not found in header row."
            )

        # Assume the index column is full and count the entries.
        index = self.worksheet.col_values(index_col_num)[self.header :]
        self._update_row_lookup(index)

        num_entries = len(index)
        body_cells = self._rowcols_range(
            start = (self.header + 1, self.col_indent + 1),
            end = (self.header + num_entries, self.col_indent + len(self.col_lookup.index)),
        )

        data = {}
        for column in self.col_lookup.index:
            if not use_columns or column in use_columns:
                data[column] = [None for i in range(num_entries)]

        for cell in body_cells:
            column = self.col_lookup.index[cell.col - self.col_indent - 1]
            if not use_columns or column in use_columns:
                val = self._get_cell_val(cell)

                if val is not None and val not in self.na_values:
                    if column in self.dtype.keys():
                        val = self.dtype[column](val)
                    else:
                        val = gspread.utils.numericise(val)

                    data[column][cell.row - self.header - 1] = val
        return data

    def read(self, names=None, use_columns=None):
        """
        Read in information from a Google document storing entries. Fields present are defined in 'names'

        :param names: list of names to give to the columns (in case they aren't present in the spreadsheet). Default None (for None, the column headers are read from the spreadsheet.
        :type names: list
        :param use_columns: return a subset of the columns.
        :type use_columns: list
        """

        # todo: need to check if something is written below the 'table' as this will be read (for example a rogue entry in the row below the last row of the data.
        column_names = self.read_headers()

        data = self.read_body(use_columns=use_columns)
        # if len(data[index_field])>len(set(data[index_field])):
        #    raise ValueError("Invalid index column, entries are not unique")
        return pd.DataFrame(data).set_index(self.index_field)

        #         except KeyError:
        #             print(("KeyError, unidentified key in ", self.worksheet_name, " in Google spreadsheet ", self.url))
        #             ans = input('Try and fix the error on the sheet and then return here. Error fixed (Y/N)?')
        #             if ans[0]=='Y' or ans[0] == 'y':
        #                 return self.read(names, header, na_values, read_values, dtype, use_columns, index_field)
        #             else:
        #                 raise KeyError("Unidentified key in " + self.worksheet_name + " in Google spreadsheet " + self.url)

    def delete_sheet(self, worksheet_name):
        """Delete the worksheet with the given name."""
        self.sheet.del_worksheet(entry)

    def update_sheet_list(self):
        """Update object with the worksheet feed and the list of worksheets, can only be run once there is a gspread client (gs_client) in place. Needs to be rerun if a worksheet is added."""
        self.worksheets = self.sheet._sheet_list

    def _repr_html_(self):
        output = '<p><b>{title}</b> at <a href="{url}" target="_blank">this url.</a>\n</p>'.format(
            url=self.url, title=self.title
        )
        return output + self.read()._repr_html_()
    

    #######################################################################
    # Place methods here that are really associated with the resource. #
    #######################################################################
    @property
    def id(self):
        return self.resource._id
    
    @property
    def title(self):
        """Get the title of the google spreadsheet."""
        return self.resource.get_name()

    @title.setter
    def title(self, title):
        """Change the title of the google spreadsheet."""
        self.resource.update_name(title)


    def share(
        self,
        users,
        share_type="writer",
        send_notifications=False,
        email_message=None,
    ):
        """
        Share a document with a given list of users.
        """
        warnings.warn(
            "Sharing should be performed on the drive class.", DeprecationWarning
        )
        self.resource.share(users, share_type, send_notifications, email_message)

    def share_delete(self, user):
        """
        Remove sharing from a given user.
        """
        warnings.warn(
            "Sharing should be performed on the drive class.", DeprecationWarning
        )
        return self.resource.share_delete(user)

    def share_modify(self, user, share_type="reader", send_notifications=False):
        """
        :param user: email of the user to update.
        :type user: string
        :param share_type: type of sharing for the given user, type options are 'reader', 'writer', 'owner'
        :type user: string
        :param send_notifications: 
        """
        warnings.warn(
            "Sharing should be performed on the drive class.", DeprecationWarning
        )

        self.resource.share_modify(user, share_type, send_notifications)

    def _permission_id(self, user):
        return self.resource._permission_id(user)

    def share_list(self):
        """
        Provide a list of all users who can access the document in the form of 
        """
        warnings.warn(
            "Sharing should be performed on the drive class.", DeprecationWarning
        )

        return self.resource.share_list()

    def revision_history(self):
        """
        Get the revision history of the document from Google Docs.
        """
        warnings.warn(
            "Revision history should be performed on the drive class.",
            DeprecationWarning,
        )
        return self.resource.revision_history()

    def ispublished(self):
        """Find out whether or not the spreadsheet has been published."""
        return self.resource.ispublished()
        
