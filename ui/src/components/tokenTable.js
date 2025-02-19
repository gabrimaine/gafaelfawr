// Render a list of tokens in tabular form.

import React, { useMemo } from 'react';
import PropTypes from 'prop-types';
import { useTable } from 'react-table';
import { FaTrash } from 'react-icons/fa';

import Timestamp from './timestamp';
import Token from './token';
import TokenName from './tokenName';

const DeleteTokenButton = function ({ token, onDeleteToken }) {
  const onClick = () => {
    onDeleteToken(token);
  };
  return (
    <button type="button" className="qa-token-delete" onClick={onClick}>
      <FaTrash />
    </button>
  );
};
DeleteTokenButton.propTypes = {
  token: PropTypes.string.isRequired,
  onDeleteToken: PropTypes.func.isRequired,
};

const TokenTable = function ({ id, data, onDeleteToken, includeName = false }) {
  const columns = useMemo(() => {
    const tokenBase = [
      {
        Header: 'Token',
        // eslint-disable-next-line react/display-name, react/prop-types
        Cell: ({ value }) => <Token token={value} />,
        accessor: 'token',
      },
      {
        Header: 'Scopes',
        Cell: ({ value }) => value.join(', '),
        accessor: 'scopes',
      },
      {
        Header: 'Created',
        // eslint-disable-next-line react/display-name, react/prop-types
        Cell: ({ value }) => <Timestamp timestamp={value} />,
        accessor: 'created',
      },
      {
        Header: 'Expires',
        // eslint-disable-next-line react/display-name, react/prop-types
        Cell: ({ value }) => (
          <Timestamp timestamp={value} className="qa-expires" expiration />
        ),
        accessor: 'expires',
      },
    ];
    const tokenName = [
      {
        Header: 'Name',
        // eslint-disable-next-line react/display-name, react/prop-types
        Cell: ({ value }) => <TokenName name={value} />,
        accessor: 'token_name',
      },
    ];
    const tokenDelete = [
      {
        id: 'delete',
        Header: '',
        // eslint-disable-next-line react/display-name, react/prop-types
        Cell: ({ value }) => (
          <DeleteTokenButton token={value} onDeleteToken={onDeleteToken} />
        ),
        accessor: 'token',
      },
    ];
    const partial = (includeName ? tokenName : []).concat(tokenBase);
    return partial.concat(tokenDelete);
  }, [includeName, onDeleteToken]);

  const table = useTable({ columns, data });

  const { getTableProps, getTableBodyProps, headerGroups, rows, prepareRow } =
    table;

  /* eslint-disable react/jsx-props-no-spreading */
  return (
    <table {...getTableProps()} id={id}>
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
            <tr {...row.getRowProps()} className="qa-token-row">
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
};
TokenTable.propTypes = {
  id: PropTypes.string.isRequired,
  data: PropTypes.arrayOf(PropTypes.object).isRequired,
  onDeleteToken: PropTypes.func.isRequired,
  includeName: PropTypes.bool,
};

export default TokenTable;
