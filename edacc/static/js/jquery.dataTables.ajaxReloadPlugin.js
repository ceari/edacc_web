$.fn.dataTableExt.oApi.fnReloadAjax = function ( oSettings, sNewSource, fnCallback, bStandingRedraw )
{
    if ( typeof sNewSource != 'undefined' && sNewSource != null )
    {
            oSettings.sAjaxSource = sNewSource;
    }
    this.oApi._fnProcessingDisplay( oSettings, true );
    var that = this;
    var iStart = oSettings._iDisplayStart;

    oSettings.fnServerData( oSettings.sAjaxSource, null, function(json) {
            var before = oSettings._iDisplayStart;
            /* Clear the old information from the table */
            that.oApi._fnClearTable( oSettings );

            /* Got the data - add it to the table */
            for ( var i=0 ; i<json.aaData.length ; i++ )
            {
                    that.oApi._fnAddData( oSettings, json.aaData[i] );
            }

            oSettings.aiDisplay = oSettings.aiDisplayMaster.slice();
            that.fnDraw( that );
            that.oApi._fnProcessingDisplay( oSettings, false );

            oSettings._iDisplayStart = before;
            oSettings.oApi._fnCalculateEnd(oSettings);
            oSettings.oApi._fnDraw(oSettings);


            /* Callback user function - for event handlers etc */
            if ( typeof fnCallback == 'function' )
            {
                    fnCallback( oSettings );
            }
    } );
}