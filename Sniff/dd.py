
import dash 
import dash_core_components as dcc 
import dash_html_components as html 

# from this file, like this: 
text_markdown = "\t"
this_file = open('Logs/nbi_measure.log','r')
lines = this_file.readlines()
for a in lines:
    text_markdown += a+'\n'

# to app 

app = dash.Dash(__name__) 

app.layout = html.Div([
                html.Div([
                           dcc.Markdown(text_markdown)
                ])
])



if __name__=='__main__':
    PORT = 8050
    SERVER='10.5.1.4'
    app.run_server(port=PORT,host=SERVER)
