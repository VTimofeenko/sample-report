# -*- coding: utf-8 -*-
#
# Copyright (c) 2021, Vladimir Timofeenko
# All rights reserved.

# This is a very simple implementation, additional customer- and reseller- related fields
# can be added

from connect.client import R

HEADERS = ("Subscription ID", "Customer ID", "Quantity", "Calculation")
# See the diagram in the repo to view axioms based on which the code is written


def generate(
    client=None,
    input_data=None,
    progress_callback=None,
    renderer_type="xlsx",
    extra_context_callback=None,
):
    """
    Extracts data from Connect using the ConnectClient instance
    and input data provided as arguments, applies
    required transformations (if any) and returns the data rendered
    by the given renderer on the arguments list.
    Some renderers may require extra context data to generate the report
    output, for example in the case of the Jinja2 renderer...

    :param client: An instance of the CloudBlue Connect
                    client.
    :type client: cnct.ConnectClient
    :param input_data: Input data used to calculate the
                        resulting dataset.
    :type input_data: dict
    :param progress_callback: A function that accepts t
                                argument of type int that must
                                be invoked to notify the progress
                                of the report generation.
    :type progress_callback: func
    :param renderer_type: Renderer required for generating report
                            output.
    :type renderer_type: string
    :param extra_context_callback: Extra content required by some
                            renderers.
    :type extra_context_callback: func
    """
    parameters = input_data
    # This report implementation is based on axiom "PR 1-1 subscription"
    sold_assets = _get_requests(client, parameters)
    total = sold_assets.count()
    progress = 0
    cost_price_delta = _get_delta(client)

    for asset in sold_assets:
        yield _process_line(asset["asset"], cost_price_delta)
        progress += 1
        progress_callback(progress, total)


def _get_requests(client, parameters):
    """Retrieves the subscriptions and quantities for which there were purchases in the period"""
    query = R()

    # will only need purchase requests
    query &= R().type.eq("purchase")
    # will only need approved requests
    query &= R().status.eq("approved")
    # only for my product
    query &= R().asset.product.id.eq("PRD-620-226-877")

    if parameters.get("date") and parameters["date"]["after"] != "":
        # this assumes that the payment is remitted at time of creation
        # probably a more real-life implementation would rely on effective_date
        query &= R().created.ge(parameters["date"]["after"])
        query &= R().created.le(parameters["date"]["before"])

    return client.requests.filter(query)


def _get_delta(client) -> int:
    """Retrieves the delta between price and cost for a specific product.

    The implementation is using a few hardcoded values"""

    price_points = list(
        client.ns("pricing")
        .versions["PLV-762-354-876-0001"]  # hardcoded price list version, "4T" price list with four price points
        .points.filter(item__global_id="PRD-620-226-877-0001")  # hardcoded to filter out irrelevant skus
        .values_list("attributes")
    )[0]

    # In this case, price is the price towards distributor, v.custom_1 is the internal cost
    return int(price_points["attributes"]["price"] - price_points["attributes"]["v.custom_1"])


def _process_line(asset: dict, cost_price_delta: int):
    """The function that builds out the report line by line"""
    try:
        qty = int(asset["items"][0]["quantity"])  # [0] to filter out irrelevant skus
    except IndexError:
        # to handle some older requests without items
        qty = 0
    return (asset["id"], asset["tiers"]["customer"]["id"], qty, cost_price_delta * qty)
