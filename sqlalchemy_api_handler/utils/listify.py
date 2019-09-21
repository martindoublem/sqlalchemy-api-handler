from sqlalchemy import text
from sqlalchemy_api_handler import ApiErrors, as_dict
from sqlalchemy_api_handler.mixins.soft_deletable_mixin import SoftDeletableMixin

class paginate_obj:
    """ Pagination dummy object. Takes a list and paginates it similar to sqlalchemy paginate() """
    def __init__(self, paginatable, page, per_page):
        self.has_next = (len(paginatable)/per_page) > page
        self.has_prev = bool(page - 1)
        self.next = page + self.has_next
        self.prev = page - self.has_prev
        self.items = paginatable[(page-1)*(per_page):(page)*(per_page)]

def query_with_order_by(query, order_by):
    if order_by:
        if type(order_by) == str:
            order_by = text(order_by)
        try:
            order_by = [order_by] if not isinstance(order_by, list) \
                else order_by
            query = query.order_by(*order_by)
        except ProgrammingError as e:
            field = re.search('column "?(.*?)"? does not exist', e._message, re.IGNORECASE)
            if field:
                errors = ApiErrors()
                errors.add_error('order_by', 'order_by value references an unknown field : ' + field.group(1))
                raise errors
            else:
                raise e
    return query

def elements_by_with_computed_ranking(query, order_by):
    elements = sorted(
        query.all(),
        key=order_by
    )
    return elements

def check_single_order_by_string(order_by_string):
    order_by_string = order_by_string.strip(' ')
    optional_table_prefix = '("?\\w+"?\\.|)'
    column_identifier = '"?\\w+"?'
    optional_sorting_order = '(|\\s+desc|\\s+asc)'
    if not re.match(f'^{optional_table_prefix}{column_identifier}{optional_sorting_order}$',
                    order_by_string,
                    re.IGNORECASE):
        api_errors = ApiErrors()
        api_errors.add_error('order_by',
                             'Invalid order_by field : "%s"' % order_by_string)
        raise api_errors

def order_by_is_native_sqlalchemy_clause(order_by):
    return isinstance(order_by, UnaryExpression) \
           or isinstance(order_by, InstrumentedAttribute) \
           or isinstance(order_by, random)

def check_order_by(order_by):
    if isinstance(order_by, list):
        for part in order_by:
            check_order_by(part)
    elif order_by_is_native_sqlalchemy_clause(order_by):
        pass
    elif isinstance(order_by, str):
        order_by = re.sub('coalesce\\((.*?)\\)',
                          '\\1',
                          order_by,
                          flags=re.IGNORECASE)
        for part in order_by.split(','):
            check_single_order_by_string(part)

def listify(
    modelClass,
    query=None,
    refine=None,
    order_by=None,
    includes=(),
    print_elements=None,
    paginate=None,
    page=None,
    populate=None
):
    if query is None:
        query = modelClass.query

    if issubclass(modelClass, SoftDeletableMixin):
        query = query.filter_by(isSoftDeleted=False)

    if refine:
        query = refine(query)

    is_already_queried = False
    if order_by:
        check_order_by(order_by)
        if type(order_by).__name__ != 'function':
            query = query_with_order_by(query, order_by)
        else:
            elements = elements_by_with_computed_ranking(query, order_by)
            is_already_queried = True

    if paginate:
        if page is not None:
            page = int(page)

        if is_already_queried:
            pagination = paginate_obj(elements, page, paginate)
        else:
            pagination = query.paginate(page, per_page=paginate, error_out=False)\

        query = pagination.items

    elements = [as_dict(o, includes=includes) for o in query]

    if populate:
        objects = list(map(populate, objects))

    if print_elements:
        print(elements)

    return elements