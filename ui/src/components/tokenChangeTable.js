import PropTypes from 'prop-types';
import React, { useMemo } from 'react';
import { useTable } from 'react-table';

import Timestamp from './timestamp';
import Token from './token';

export default function TokenChangeTable({ data, includeToken = false }) {
  const columns = useMemo(() => {
    const prefix = [
      {
        Header: 'Event Time',
        // eslint-disable-next-line react/display-name, react/prop-types
        Cell: ({ value }) => <Timestamp timestamp={value} past />,
        accessor: 'event_time',
      },
      {
        Header: 'Action',
        accessor: 'action',
      },
      {
        Header: 'Actor',
        accessor: 'actor',
      },
      {
        Header: 'IP Address',
        accessor: 'ip_address',
      },
    ];
    const token = [
      {
        Header: 'Token',
        // eslint-disable-next-line react/display-name, react/prop-types
        Cell: ({ value }) => <Token token={value} />,
        accessor: 'token',
      },
    ];
    const suffix = [
      {
        Header: 'Token Name',
        accessor: 'token_name',
      },
      {
        Header: 'Old Token Name',
        accessor: 'old_token_name',
      },
      {
        Header: 'Scopes',
        // eslint-disable-next-line react/prop-types
        Cell: ({ value }) => (value ? value.join(', ') : null),
        accessor: 'scopes',
      },
      {
        Header: 'Old Scopes',
        // eslint-disable-next-line react/prop-types
        Cell: ({ value }) => (value ? value.join(', ') : null),
        accessor: 'old_scopes',
      },
      {
        Header: 'Expires',
        // eslint-disable-next-line react/display-name, react/prop-types
        Cell: ({ value }) => <Timestamp timestamp={value} past={false} />,
        accessor: 'expires',
      },
      {
        Header: 'Old Expires',
        // eslint-disable-next-line react/display-name, react/prop-types
        Cell: ({ value }) => <Timestamp timestamp={value} past={false} />,
        accessor: 'old_expires',
      },
    ];
    if (includeToken) {
      return prefix.concat(token).concat(suffix);
    }
    return prefix.concat(suffix);
  }, [includeToken]);

  const table = useTable({ columns, data });

  const { getTableProps, getTableBodyProps, headerGroups, rows, prepareRow } =
    table;

  if (!data.length) return <p>No results</p>;

  /* eslint-disable react/jsx-props-no-spreading */
  return (
    <table {...getTableProps()}>
      <thead>
        {headerGroups.map((headerGroup) => (
          <tr {...headerGroup.getHeaderGroupProps()}>
            {headerGroup.headers.map((column) => (
              <th {...column.getHeaderProps()}>{column.render('Header')}</th>
            ))}
          </tr>
        ))}
      </thead>
      <tbody {...getTableBodyProps()}>
        {rows.map((row) => {
          prepareRow(row);
          return (
            <tr {...row.getRowProps()} className="qa-token-change-row">
              {row.cells.map((cell) => (
                <td {...cell.getCellProps()}>{cell.render('Cell')}</td>
              ))}
            </tr>
          );
        })}
      </tbody>
    </table>
  );
  /* eslint-enable react/jsx-props-no-spreading */
}
TokenChangeTable.propTypes = {
  data: PropTypes.arrayOf(PropTypes.object).isRequired,
  includeToken: PropTypes.bool,
};
