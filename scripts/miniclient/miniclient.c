#include <my_global.h>
#include <mysql.h>
#include <stdlib.h>
#include <stdio.h>
#include <unistd.h>

const char * LOCK_JOB = "UDPATE ExperimentResults SET status=0 WHERE idJob=%d;";

/*int fetchJob_RANDOM_LIMIT(MYSQL* conn, int experiment_id) {
    const char* SELECT_Q = "SELECT idJob FROM ExperimentResults WHERE status < 0 AND Experiment_idExperiment = %d LIMIT %d,1 FOR UPDATE;";
    char* query = calloc(1, 512);
    sprintf(query, SELECT_Q, experiment_id, rand() % 2000);
    if (mysql_query(conn, query) != 0) {
        printf("%s\n", mysql_error(conn));
        exit(1);
    }
    free(query);
    MYSQL_RES* result = mysql_store_result(conn);
    if (mysql_num_rows(result) < 1) {
        mysql_free_result(result);
        return -1;
    }
    MYSQL_ROW row = mysql_fetch_row(result);
    mysql_free_result(result);
    int idJob = atoi(row[0]);
    
    query = calloc(1, 256);
    sprintf(query, LOCK_JOB, idJob);
    mysql_query(conn, query);
    free(query);
    mysql_commit(conn);
    return idJob;
}*/

/* int fetchJob_UPDATE(MYSQL* conn, int experiment_id) { // buggy
    char * UPDATE_QUERY = "UPDATE ExperimentResults SET status=0 WHERE Experiment_idExperiment=%d AND status=-1 AND idJob = (@update_id := idJob) LIMIT 1;";
    char * query = calloc(1, 256);
    sprintf(query, UPDATE_QUERY, experiment_id);
    mysql_query(conn, query);
    free(query);
    char * SELECT_QUERY = "SELECT @update_id;";
    query = calloc(1, 256);
    sprintf(query, SELECT_QUERY);
    mysql_query(conn, query);
    mysql_commit(conn);
    free(query);
    MYSQL_RES* result = mysql_store_result(conn);
    if (mysql_num_rows(result) < 1) {
        mysql_free_result(result);
        return -1;
    }
    MYSQL_ROW row = mysql_fetch_row(result);
    int idJob = atoi(row[0]);
    mysql_free_result(result);
    return idJob;
}*/

int fetchJob_FLOOR_LOCK(MYSQL* conn, int experiment_id) {
    const char* SELECT_QUERY = "SELECT FLOOR(RAND()*COUNT(idJob)) as x FROM ExperimentResults \
                                 WHERE Experiment_idExperiment=%d AND status < 0;";
    char* query = calloc(1, 256);
    sprintf(query, SELECT_QUERY, experiment_id);
    mysql_query(conn, query);
    free(query);
    MYSQL_RES* result = mysql_store_result(conn);
    if (mysql_num_rows(result) < 1) {
        mysql_free_result(result);
        return -1;
    }
    MYSQL_ROW row = mysql_fetch_row(result);
    mysql_free_result(result);
    int limit = atoi(row[0]);

    const char * LOCK_QUERY = "SELECT idJob FROM ExperimentResults WHERE Experiment_idExperiment=%d \
                             AND status < 0 LIMIT %d,1 FOR UPDATE;";

    query = calloc(1, 256);
    sprintf(query, LOCK_QUERY, experiment_id, limit);
    mysql_query(conn, query);
    free(query);
    result = mysql_store_result(conn);
    if (mysql_num_rows(result) < 1) {
        mysql_free_result(result);
        return -1;
    }
    row = mysql_fetch_row(result);
    mysql_free_result(result);
    int idJob = atoi(row[0]);
    
    query = calloc(1, 256);
    sprintf(query, LOCK_JOB, idJob);
    mysql_query(conn, query);
    free(query);
    mysql_commit(conn);
    return idJob;
}

int fetchJob_ORDER_BY_RAND(MYSQL* conn, int experiment_id) {
    const char * SINGLE_LOCK_QUERY = "SELECT idJob FROM ExperimentResults WHERE Experiment_idExperiment=%d \
                                      AND status<0 ORDER BY RAND() LIMIT 1 FOR UPDATE;";
    char * query = calloc(1, 256);
    sprintf(query, SINGLE_LOCK_QUERY, experiment_id);
    mysql_query(conn, query);
    free(query);
    MYSQL_RES* result = mysql_store_result(conn);
    if (mysql_num_rows(result) < 1) {
        mysql_free_result(result);
        return -1;
    }
    MYSQL_ROW row = mysql_fetch_row(result);
    int idJob = atoi(row[0]);
    mysql_free_result(result);
    
    query = calloc(1, 256);
    sprintf(query, LOCK_JOB, idJob);
    mysql_query(conn, query);
    free(query);
    mysql_commit(conn);
    return idJob;
}

int fetchJob_FIRST_FREE(MYSQL* conn, int experiment_id) {
    char * query = calloc(1, 256);
    sprintf(query, "SELECT idJob FROM ExperimentResults WHERE status<0 AND \
            Experiment_idExperiment=%d LIMIT 1 FOR UPDATE", experiment_id);
    mysql_query(conn, query);
    free(query);
    MYSQL_RES* result = mysql_store_result(conn);
    if (mysql_num_rows(result) < 1) {
        mysql_free_result(result);
        return -1;
    }
    MYSQL_ROW row = mysql_fetch_row(result);
    int idJob = atoi(row[0]);
    mysql_free_result(result);

    query = calloc(1, 256);
    sprintf(query, LOCK_JOB, idJob);
    mysql_query(conn, query);
    free(query);
    mysql_commit(conn);
    return idJob;
}

void processJob(MYSQL* conn, int idJob) {
    const char * FINISH_JOB = "UPDATE ExperimentResults SET status=1, resultCode=11 WHERE idJob=%d;"; 
    char* query = calloc(1, 256);
    sprintf(query, FINISH_JOB, idJob);
    mysql_query(conn, query);
    free(query);
    mysql_commit(conn);
}

int num_jobs(MYSQL* conn, int experiment_id, int status) {
    char* query = calloc(1, 256);
    sprintf(query, "SELECT COUNT(idJob) FROM ExperimentResults WHERE Experiment_idExperiment=%d \
            AND status=%d;", experiment_id, status);
    mysql_query(conn, query);
    free(query);
    MYSQL_RES* result = mysql_store_result(conn);
    MYSQL_ROW row = mysql_fetch_row(result);
    int num = atoi(row[0]);
    mysql_free_result(result);
    return num;
}

int main(int argc, char* argv[]) {
    char* db_user = argv[1];
    char* db_passw = argv[2];
    char* db_name = argv[3];
    char* db_host = argv[4];
    int num_clients = atoi(argv[5]);
    int job_method = atoi(argv[6]);
    int experiment_id = atoi(argv[7]);
    if (argc < 8) {
        printf("Too few arguments to miniclient!\n");
        printf("Usage: miniclient <user> <password> <db name> <host> <num clients> <job method> <experiment id>\n");
        exit(1);
    }

    int (*fetchJob)(MYSQL*, int);
    if (job_method == 0) fetchJob = fetchJob_FLOOR_LOCK;
    else if (job_method == 1) fetchJob = fetchJob_ORDER_BY_RAND;
    else if (job_method == 2) fetchJob = fetchJob_FIRST_FREE;

    MYSQL* conn = mysql_init(NULL);
    if (mysql_real_connect(conn, db_host, db_user, db_passw, db_name, 3306, NULL, 0) == NULL) {
        printf("Error connecting to DB: %s\n", mysql_error(conn));
        exit(1);
    }
    mysql_close(conn);

    int pid;
    for (int i = 0; i < num_clients; i++) {
        pid = fork();
        if (pid == 0) break; // child
    }

    if (pid == 0) { // child, process jobs
        conn = mysql_init(NULL);
        if (mysql_real_connect(conn, db_host, db_user, db_passw, db_name, 3306, NULL, 0) == NULL) {
            printf("Error connecting to DB: %s\n", mysql_error(conn));
            exit(1);
        }
        mysql_autocommit(conn, 0);
        int idJob;
        while ((idJob = fetchJob(conn, experiment_id)) >= 0) {
            processJob(conn, idJob);
        }
    }
    else { // parent, monitor progress
        conn = mysql_init(NULL);
        if (mysql_real_connect(conn, db_host, db_user, db_passw, db_name, 3306, NULL, 0) == NULL) {
            printf("Error connecting to DB: %s\n", mysql_error(conn));
            exit(1);
        }
        int finished = num_jobs(conn, experiment_id, 1);
        int time = 0;
        while (1) {
            sleep(2);
            int finished_now = num_jobs(conn, experiment_id, 1);
            int delta = finished_now - finished;
            printf("Time elapsed: %d - Jobs/sec: %.2f\n", time, delta / 2.0f);
            finished = finished_now;
            time += 2;
            if (num_jobs(conn, experiment_id, 0) == 0 && num_jobs(conn, experiment_id, -1) == 0) {
                break;
            }
        }
    }

    mysql_close(conn);
}
