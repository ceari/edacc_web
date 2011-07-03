//
// INTERFACE GLUE
//

bv.ui = {
    resourcesRequested: [{name: "categories", path: "{{url_for('borgexplorer.borg_explorer_data', database=database, experiment_id=experiment.idExperiment, type='categories.json')}}"}],
    resources: {}
};

bv.ui.initialize = function() {
    // enable help dialog
    $("#bv-help-dialog").dialog({ width: 700 });
    $("#bv-help-dialog").dialog("close");

    $("#bv-help-anchor").click(function(event) {
        event.preventDefault();

        $("#bv-help-dialog").dialog("open");
    });

    // enable change-category links
    var this_ = this;
    var state = bv.state.initial(this);

    d3.select("#change-data > nav")
        .selectAll("a")
        .data(this.resources.categories)
        .enter()
        .append("a")
        .attr("href", "")
        .text(function(d) { return d.name; })
        .on("click", function(d) {
            d3.event.preventDefault();

            this_.change(this_.state.withCategory(d));
        });

    // enable change-view links
    var views = d3.values(bv.views);

    d3.select("#change-view > nav")
        .selectAll("a")
        .data(views)
        .enter()
        .append("a")
        .attr("href", "")
        .text(function(d) { return d.description; })
        .on("click", function(d) {
            d3.event.preventDefault();

            this_.change(this_.state.withView(d));
        });

    // get the ball rolling
    this.change(state);
};

bv.ui.change = function(state) {
    if(this.state !== undefined) {
        this.state.destroy();
    }

    this.state = state;

    d3.selectAll("#change-data > nav > a")
        .classed("current", function(d) { return d.path === state.category.path; })

    d3.selectAll("#change-view > nav > a")
        .classed("current", function(d) { return d.description === state.viewFactory.description; })

    this.state.create();

    bv.loading.create(this.state.view);

    this.state.view.load();
};

bv.ui.request = function(name, filename) {
    return {
        name: name,
        path: "{{url_for('borgexplorer.borg_explorer_data', database=database, experiment_id=experiment.idExperiment)}}?type=" + filename
    };
};

$(bv.ui).bind("resources-loaded", function() { this.initialize(); });

bv.load(bv.ui);

