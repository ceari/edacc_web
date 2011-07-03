"use strict";

$(function() {

String.prototype.format = function() {
    var catted = [this];

    return sprintf.apply(null, catted.concat.apply(catted, arguments));
};

var bv = {
    views: {}
};

bv.load = function(loadable) {
    var remaining = loadable.resourcesRequested.length;
    var $loadable = $(loadable);

    $loadable.bind("resource-loaded", function(event, request, resource) {
        loadable.resources[request.name] = resource;

        remaining -= 1;

        if(remaining === 0) {
            $loadable.trigger("resources-loaded");
        }
    });

    loadable.resourcesRequested.forEach(function(request) {
        d3.json(request.path, function(resource) {
            $loadable.trigger("resource-loaded", [request, resource]);
        });
    });
};

bv.later = function(this_, callback) {
    setTimeout(function() { callback.call(this_); }, 0);
};

{% include "borgexplorer/views/cluster.js" %}
{% include "borgexplorer/views/table.js" %}
{% include "borgexplorer/core/list.js" %}
{% include "borgexplorer/core/state.js" %}
{% include "borgexplorer/core/loading.js" %}
{% include "borgexplorer/core/bar_chart.js" %}
{% include "borgexplorer/core/ui.js" %}

});

